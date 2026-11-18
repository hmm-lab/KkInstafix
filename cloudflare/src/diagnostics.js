import {PROVIDERS} from './config.js';
import {urls,processText,duplicateDestination,trim,rewritePlatform,escapeHTML as h} from './links.js';
import {messageSource} from './messages.js';
import {healthLabel} from './provider-policy.js';
import {hash} from './security.js';

// Diagnostics expose parameter names, never their values or URL credentials.
export function diagnosticURL(raw) {
  try {
    const u=new URL(trim(raw)[0]);u.username='';u.password='';
    for(const key of [...u.searchParams.keys()])u.searchParams.set(key,'[kept]');
    if(u.hash)u.hash='[present]';
    return u.href.slice(0,180)+(u.href.length>180?'…':'');
  }catch{return '(invalid URL)';}
}
const keys=raw=>{try{return [...new URL(trim(raw)[0]).searchParams.keys()];}catch{return [];}};
const names=values=>[...new Set(values)].slice(0,12).map(s=>h(s.slice(0,50))).join(', ')||'none';
export async function diagnose(msg,argumentsText,store,tg) {
  const chat=msg.chat.id,stamp=Math.floor(Date.now()/1000);
  let target=msg.reply_to_message,source=target?messageSource(target):argumentsText,user=target?.from?.id??msg.from?.id??0;
  let bot=target?.from?.is_bot??false,forwarded=!!target?.forward_origin,old=false;
  if(target) {
    const snapshot=await store.original(chat,target.message_id);
    if(snapshot) {
      const original=JSON.parse(snapshot.original_json);source=messageSource(original);user=original.user_id;bot=false;forwarded=original.forwarded;
    }else {
      const prior=await store.rewrite(chat,target.message_id);
      if(prior){source=prior.original_url;user=msg.from?.id??0;bot=false;old=true;}
    }
  }
  const state=await store.settings(chat,user),settings=state.settings;
  const input=[...new Set(urls(source??''))];
  const reply=text=>tg.send(chat,text,{parse_mode:'HTML',link_preview_options:{is_disabled:true},message_thread_id:msg.message_thread_id,
    reply_parameters:{message_id:msg.message_id,allow_sending_without_reply:true}});
  if(!input.length)return reply('Reply to a message containing links or use /diagnose &lt;url&gt;.');
  if(input.length>8)return reply('Decision: left unchanged — more than 8 links. Use up to 8 links per message.');
  const result=await processText(source,settings,state.choices,state.overrides,tg.net,false,state.health,store.cache);
  let reason=bot?'ignored — another bot':state.muted?'ignored — sender is muted':!settings.enabled?'ignored — bot disabled in this chat':
    state.optout?'ignored — sender opted out':settings.ignore_forwards&&forwarded?'ignored — forwarded posts are disabled':null;
  const platforms=input.map(raw=>{try{return rewritePlatform(new URL(raw));}catch{return null;}});
  if(!reason&&platforms.every(p=>p&&(state.overrides[p]??(p==='weibo'?0:1))===0))reason='ignored — platform disabled in this chat';
  if(!reason&&!result.links.length)reason='unchanged — no supported rewrite or tracking to remove';
  if(!reason) {
    const rate=await store.stmt('SELECT COUNT(*) AS n FROM rate_events WHERE chat_id=? AND user_id=? AND ts>?',chat,user,stamp-settings.rate_window).first();
    if(rate.n>=settings.rate_limit)reason='ignored for now — sender link rate limit reached';
    else {
      let fresh=false;
      for(const link of result.links) {
        const row=await store.stmt("SELECT ts FROM recent_events WHERE kind='fix' AND chat_id=? AND event_key=?",chat,await hash(duplicateDestination(link))).first();
        if(!row||row.ts<=stamp-settings.dedup_window)fresh=true;
      }
      if(!fresh)reason='ignored for now — duplicate within the dedup window';
    }
  }
  const blocks=['<b>Link diagnosis</b>','<b>If posted now:</b> '+h(reason??'would send a cleaned replacement')];
  if(old)blocks.push('Older post: original-author checks are unavailable; using your current settings.');
  for(const raw of [...new Set(input)].slice(0,8)) {
    const fixed=result.links.find(l=>trim(l.original)[0]===raw),platform=fixed?.platform??platforms[input.indexOf(raw)];
    const destination=fixed?.url??raw,preview=fixed?.preview??destination;
    const retained=keys(destination).map(k=>k.toLowerCase());
    const removed=keys(raw).filter(k=>!retained.includes(k.toLowerCase()));
    const selected=fixed?.previewKey??fixed?.key??(platform?(state.choices[platform]??PROVIDERS[platform]?.default):null);
    blocks.push(`\n<b>Destination:</b> <code>${h(diagnosticURL(destination))}</code>\n<b>Preview:</b> <code>${h(diagnosticURL(preview))}</code>\n`+
      `<b>Provider:</b> ${h(platform&&selected?platform+'/'+selected:'native / generic cleanup')}\n`+
      `<b>Removed parameters:</b> ${names(removed)}\n<b>Retained parameters:</b> ${names(keys(destination))}`+
      (platform&&selected?'\n<b>Background check:</b> '+h(selected==='native'?'native preview':healthLabel(state.health[platform]?.[selected],stamp)):''));
  }
  blocks.push('\nQuery values are hidden. Background metadata checks do not confirm playback in your Telegram client.');
  let part='';
  for(const block of blocks) {
    if(part.length+block.length+1>3800){await reply(part);part='<b>Link diagnosis (continued)</b>\n';}
    part+=(part?'\n':'')+block;
  }
  return reply(part);
}
