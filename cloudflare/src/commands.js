import {VERSION} from './version.js';
import {postCallback} from './posts.js';
import {musicLink} from './music.js';
import {budgetStatus} from './status.js';
import {permissionStatus} from './status.js';
import {hasProtectedLinks} from './formatting.js';
import {diagnose} from './diagnostics.js';
import {nextHealthy,healthLabel} from './provider-policy.js';
import {PROVIDERS,PLATFORM_EMOJI,PROVIDER_REVISION} from './config.js';
import {processText,urls,fixedFor,escapeHTML as h,senderLabel} from './links.js';
import {validSetting,validAppearance} from './store.js';
import {hash} from './security.js';
import {BACKUP_LIMIT, importBackup} from './backup.js';
import {messageSource,messageLinks,renderLinkedText,providerMatches,linkIdentity} from './messages.js';

const ADMIN=new Set(['ping','menu','enable','disable','muteuser','unmuteuser','listmuted','resetproviders',
  'setprovider','platform','setsendermode','setdedup','setratelimit','ignoreforwards','fallback','textspam',
  'resetstats','testall','export','import']);
const onOff=s=>['on','true','yes','1'].includes(s)?1:['off','false','no','0'].includes(s)?0:null;
export function cycleKeyboard(platform,index,target='',active=null) {
  const keys=Object.keys(PROVIDERS[platform]?.options??{}).filter(k=>!Object.hasOwn(PROVIDERS[platform].noauth_embed??{},k));
  const effective=PROVIDERS[platform]?.noauth_embed?.[active]??active;
  const retry={text:active?`↻ Retry · ${effective==='native'?'Native':effective.toUpperCase()} · ${Math.max(0,keys.indexOf(effective))+1}/${keys.length}`:'↻ Retry preview',callback_data:`e:${platform}:${index}${target?':'+target:''}`};
  return {inline_keyboard:[[retry]]};
}
const platformName=p=>({twitter:'X / Twitter',piviv:'Pixiv',xiaohongshu:'Xiaohongshu (RED)',youtube:'YouTube',tiktok:'TikTok',ifunny:'iFunny',furaffinity:'FurAffinity'}[p]??p[0].toUpperCase()+p.slice(1));
function platformKeyboard(choices,page=0) {
  const platforms=Object.keys(PROVIDERS).sort((a,b)=>platformName(a).localeCompare(platformName(b))),pages=Math.ceil(platforms.length/6);
  page=Math.max(0,Math.min(pages-1,Number.isInteger(page)?page:0));
  const rows=platforms.slice(page*6,page*6+6).map(p=>[{text:`${platformName(p)} · ${(choices[p]??PROVIDERS[p].default).toUpperCase()}`,callback_data:`m:p:${p}`}]);
  rows.push([...(page>0?[{text:'‹ Previous',callback_data:`m:list:${page-1}`}]:[]),{text:`${page+1}/${pages}`,callback_data:`m:list:${page}`},...(page<pages-1?[{text:'Next ›',callback_data:`m:list:${page+1}`}]:[])]);
  return {inline_keyboard:rows};
}
function providerKeyboard(platform,chosen) {
  return {inline_keyboard:[...Object.entries(PROVIDERS[platform].options).map(([k,host])=>[{text:`${k===chosen?'✓ ':''}${k==='native'?'Native':k.toUpperCase()} · ${host}`,callback_data:`m:s:${platform}:${k}`}]),[{text:'‹ Platforms',callback_data:'m:back'}]]};
}
const HELP=`<b>KkInstafix</b>\nSend a social link to fix its Telegram preview. Tap “Retry preview” to try another provider. On multi-link posts, the sender or an admin can select which link gets the preview.\n\n`+
  `<b>Your controls</b>\n/optout · /optin — leave your links unchanged / resume fixing\n/clean &lt;url&gt; — strip tracking\n/preview &lt;url&gt; — inspect a rewrite\n/diagnose &lt;url&gt; — explain cleanup, provider and ignored posts\n/refresh — reply to a fixed post to refresh the same provider\n/repair — reply to check alternatives on demand\n/music &lt;url&gt; — share across music services\n/appearance — your attribution and compact preview settings\n/undo — restore the full original message (new posts)\n/providers · /status · /stats · /version\n\n`+
  `<b>Admin controls</b>\n/menu · /enable · /disable\n/setprovider &lt;platform&gt; &lt;key&gt;\n/platform &lt;name&gt; on|off\n/setsendermode first_name|username|full_name|none\n/setdedup &lt;seconds&gt;\n/setratelimit &lt;count&gt; &lt;seconds&gt;\n/ignoreforwards on|off · /fallback on|off · /textspam on|off\n/muteuser · /unmuteuser · /listmuted\n/resetproviders · /resetstats · /testall\n/export · /import\n\nUse @KkInstaFixBot &lt;link&gt; inline in any chat.`;
export async function command(msg,store,tg,state,ctx={}) {
  const text=(msg.text??msg.caption??'').trim(), parts=text.split(/\s+/), name=parts[0].split('@')[0].slice(1).toLowerCase();
  const addressed=parts[0].split('@')[1];
  const linkArguments = () => messageSource(msg).trim().slice(parts[0].length).trimStart();
  if(addressed&&addressed.toLowerCase()!==tg.username?.toLowerCase())return;
  const chat=msg.chat.id,user=msg.from?.id??0;
  const reply=(text,extra={})=>tg.send(chat,text,{parse_mode:'HTML',reply_parameters:{message_id:msg.message_id,allow_sending_without_reply:true},message_thread_id:msg.message_thread_id,...extra});
  if (ADMIN.has(name) && !await tg.admin(chat,user,msg.chat.type)) return reply('Only admins can use that command.');
  const p=parts[1]?.toLowerCase(), k=parts[2]?.toLowerCase();
  if (['start','help'].includes(name)) return reply(HELP);
  if (['version','ping'].includes(name)) return reply(`KkInstafix v${VERSION} · Cloudflare Workers + D1`);
  if (['about','credits','me'].includes(name)) return reply('💖 <b>About this bot</b>\nMy name is Mehrab and I love you Motki 🥰\n\nThis bot fixes social links so they embed in Telegram. Thanks to the community-maintained embed providers.\n\nMade with love by Mehrab 💖');
  if (['mehrab','mo','genius'].includes(name)) return tg.call(name==='genius'?'sendVideo':'sendPhoto',{
    chat_id:chat,[name==='genius'?'video':'photo']:`https://raw.githubusercontent.com/hmm-lab/KkInstafix/main/${name==='genius'?'genius.mp4':'30364.jpg'}`,message_thread_id:msg.message_thread_id});
  if (name==='testcb') return reply('Callback test',{reply_markup:{inline_keyboard:[[{text:'Test',callback_data:'test'}]]}});
  if (['optout','optin'].includes(name)) {
    if (!user) return reply('This command needs an identifiable user.');
    await store.opt(chat,user,name==='optout');
    return reply(name==='optout'?'Your links will be left unchanged in this chat. Others can still use the bot.':'Your links will be fixed again in this chat.');
  }
  if (name==='status'||name==='config') return reply((await permissionStatus(msg,tg))+budgetStatus(ctx.budget)+'\n\n'+Object.entries(state.settings).filter(([key])=>key!=='chat_id').map(([key,value])=>`<b>${h(key)}</b>: ${h(value)}`).join('\n')+`\nYour links: ${state.optout?'opted out':'enabled'}`);
  if (name==='providers') return reply(`<b>Providers updated ${PROVIDER_REVISION}</b>\n\n`+Object.entries(PROVIDERS).map(([p,cfg])=>`${PLATFORM_EMOJI[p]??''} <b>${p}</b>: ${h(state.choices[p]??cfg.default)}\n  ${Object.keys(cfg.options).map(k=>k+(healthLabel(state.health[p]?.[cfg.noauth_embed?.[k]??k])==='temporarily skipped'?' ⚠':'')).join(', ')}`).join('\n'));
  if(name==='appearance') {
    if(!user)return reply('This command needs an identifiable user.');
    const scope=msg.chat.type==='private'?0:chat;
    if(p==='reset'){await store.stmt("DELETE FROM user_settings WHERE user_id=? AND chat_id=? AND key IN ('attribution','preview_size')",user,scope).run();return reply('Your appearance overrides were reset. Future posts use the inherited defaults.');}
    const key=p==='attribution'?'attribution':p==='preview'?'preview_size':null,value=key==='attribution'?onOff(k):k;
    if(key&&validAppearance(key,value)){await store.setAppearance(scope,user,key,value);return reply('Your appearance was updated for future posts'+(scope===0?' in all chats (group overrides take priority).':' in this chat.'));}
    return reply(`Your appearance: attribution ${state.settings.attribution?'on':'off'}, preview ${h(state.settings.preview_size)}.\n/appearance attribution on|off\n/appearance preview compact|large\n/appearance reset\nOnly your posts change. Set defaults in private chat, or overrides in a group.`);
  }
  if(name==='music') {
    const source=parts.slice(1).join(' ')||messageSource(msg.reply_to_message??{}),links=urls(source);
    const universal=links.map(raw=>musicLink(raw)).find(Boolean);
    if(!universal)return reply('Use /music &lt;track or album URL&gt;, or reply to one. Supported: Spotify, Apple Music, YouTube Music, Tidal, Deezer, SoundCloud, Pandora and Amazon Music.');
    return reply(`<a href="${h(universal)}">Listen on your music service</a>`,{link_preview_options:{is_disabled:false,url:universal,prefer_large_media:state.settings.preview_size!=='compact',prefer_small_media:state.settings.preview_size==='compact'}});
  }
  if(name==='refresh'||name==='repair') {
    if(!msg.reply_to_message?.message_id)return reply(`Reply to a fixed post with /${name} to ${name==='repair'?'check up to three preview providers':'request a fresh preview'}.`);
    const handled=await postCallback({from:msg.from,data:name==='repair'?'a:repair':'r:refresh',message:{...msg.reply_to_message,chat:msg.chat,message_thread_id:msg.message_thread_id},command_id:msg.message_id},store,tg,ctx);
    if(!handled)return reply('Reply to a fixed post from the last seven days. Older posts can use Retry preview.');
    return;
  }
  if(name==='diagnose')return diagnose(msg,linkArguments(),store,tg);
  if (name==='menu') return reply('<b>Provider menu</b>',{reply_markup:platformKeyboard(state.choices)});
  if (name==='setprovider') {
    if (!PROVIDERS[p]?.options[k]) return reply('Usage: /setprovider &lt;platform&gt; &lt;key&gt; — see /providers.');
    await store.choose(chat,p,k);return reply(`${h(p)} provider set to ${h(k)}.`);
  }
  if (name==='resetproviders') {await store.stmt('DELETE FROM provider_settings WHERE chat_id=?',chat).run();return reply('Providers reset to defaults.');}
  if (name==='platform') {
    if (!p) return reply(Object.keys(PROVIDERS).map(p=>`${p}: ${(state.overrides[p]??(p==='weibo'?0:1))?'on':'off'}`).join('\n'));
    if (!PROVIDERS[p]||onOff(k)===null) return reply('Usage: /platform &lt;name&gt; on|off');
    await store.override(chat,p,onOff(k));return reply(`${h(p)} rewriting ${onOff(k)?'enabled':'disabled'}.`);
  }
  if (['enable','disable'].includes(name)) {await store.setSetting(chat,'enabled',Number(name==='enable'));return reply(`Bot ${name==='enable'?'enabled':'disabled'} in this chat.`);}
  const toggle={ignoreforwards:'ignore_forwards',fallback:'provider_fallback',textspam:'text_spam'}[name];
  if (toggle) {const value=onOff(p);if(value===null)return reply(`Usage: /${name} on|off`);await store.setSetting(chat,toggle,value);return reply('Setting updated.');}
  if (['setsendermode','setdedup','setratelimit'].includes(name)) {
    const changes=name==='setsendermode'?{sender_mode:p}:name==='setdedup'?{dedup_window:Number(p)}:{rate_limit:Number(p),rate_window:Number(k)};
    if (Object.entries(changes).some(([key,v])=>!validSetting(key,v))) return reply('Invalid setting. See /help for usage.');
    for (const [key,value] of Object.entries(changes)) await store.setSetting(chat,key,value);
    return reply('Setting updated.');
  }
  if (['muteuser','unmuteuser'].includes(name)) {
    const id=msg.reply_to_message?.from?.id??Number(p);
    if (!Number.isSafeInteger(id)||id<=0) return reply('Reply to a user or pass a numeric user ID.');
    await store.mute(chat,id,name==='muteuser');return reply(`User ${id} ${name==='muteuser'?'muted':'unmuted'}.`);
  }
  if (name==='listmuted') {const rows=await store.stmt('SELECT user_id FROM blocked_users WHERE chat_id=?',chat).all();return reply(rows.results.map(r=>String(r.user_id)).join('\n')||'No muted users.');}
  if (name==='stats') {const rows=await store.stmt('SELECT platform,SUM(count) AS count FROM chat_stats WHERE chat_id=? GROUP BY platform',chat).all();return reply(rows.results.map(r=>`${h(r.platform)}: ${r.count}`).join('\n')||'No link fixes recorded yet.');}
  if (name==='resetstats') {await store.stmt('DELETE FROM chat_stats WHERE chat_id=?',chat).run();return reply('Stats reset.');}
  if(name==='undo') {
    const id=msg.reply_to_message?.message_id??0,details=await store.original(chat,id);
    if(details) {
      const original=JSON.parse(details.original_json),text=original.text??original.caption??'';
      const options={parse_mode:undefined,entities:original.entities??original.caption_entities??[],link_preview_options:{is_disabled:true}};
      if(original.media) {
        const methods={photo:'sendPhoto',video:'sendVideo',animation:'sendAnimation',document:'sendDocument',audio:'sendAudio',voice:'sendVoice'};
        const method=methods[original.media.type];
        if(method)return tg.call(method,{chat_id:chat,[original.media.type]:original.media.file_id,caption:text,
          caption_entities:original.caption_entities??[],disable_notification:true,message_thread_id:msg.message_thread_id,
          ...(['photo','video','animation'].includes(original.media.type)?{has_spoiler:original.media.has_spoiler,show_caption_above_media:original.media.show_caption_above_media}:{}),
          reply_parameters:{message_id:msg.message_id,allow_sending_without_reply:true}});
      }
      return reply(text,options);
    }
    const row=await store.rewrite(chat,id);
    return reply(row?`Original link (this older post has no full-message snapshot):\n${h(row.original_url)}`:'Reply to a rewritten message from the last 7 days.',{link_preview_options:{is_disabled:true}});
  }
  if (['clean','preview'].includes(name)) {
    const source=msg.reply_to_message?messageSource(msg.reply_to_message):linkArguments();
    if (!urls(source).length) return reply(`Reply to a link or use /${name} &lt;url&gt;.`);
    const result=await processText(source,state.settings,state.choices,state.overrides,tg.net,name==='clean',state.health,store.cache);
    if (result.tooMany) return reply('Use up to 8 links at a time. Split the links across separate messages and try again.', {link_preview_options:{is_disabled:true}});
    if (result.text.length > 4096) return reply('The result is too long for Telegram. Use fewer links at a time.', {link_preview_options:{is_disabled:true}});
    return reply(h(result.text),{link_preview_options:{is_disabled:true}});
  }
  if (name==='testall') {
    const raw=urls(parts.slice(2).join(' ')||msg.reply_to_message?.text||'')[0];
    if (!PROVIDERS[p]||!raw) return reply('Usage: /testall &lt;platform&gt; &lt;real post URL&gt;');
    // One diagnostic reply avoids a burst of messages and tests real content.
    return reply(Object.keys(PROVIDERS[p].options).map(k=>`${h(k)}: ${h(fixedFor(raw,p,k).preview)}`).join('\n'));
  }
  if (name==='export') {
    const data = JSON.stringify(await store.export(chat));
    const document = new Blob([data], {type:'application/json'});
    if (document.size > BACKUP_LIMIT) return reply('This chat’s settings exceed the 64 KiB backup limit.');
    const form = new FormData();
    form.set('chat_id', String(chat));
    form.set('document', document, `kkinstafix-chat-${chat}.json`);
    form.set('caption','Send this file back with caption /import to restore.');
    const response=await tg.net(`https://api.telegram.org/bot${tg.token}/sendDocument`,{method:'POST',body:form,signal:AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('Export delivery failed');
    return;
  }
  if (name==='import') return importBackup(msg,store,tg,reply,ctx.budget);
  return reply('Unknown command. Use /help.');
}
export async function callback(query,store,tg,ctx={}) {
  const data=query.data??'',msg=query.message,chat=msg?.chat?.id;
  if(chat&&await store.isMuted(chat,query.from?.id??0))return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Preview controls are unavailable while you are muted in this chat.'});
  if (data==='test') return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'✅ Callback works!',show_alert:true});
  if (!msg||!chat) return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Message no longer accessible.'});
  if(await postCallback(query,store,tg,ctx))return;
  if(data.startsWith('p:'))return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'These preview controls have expired. Send the link again.'});
  if (data.startsWith('e:')) {
    if(!await store.tapAllowed(chat,msg.message_id))return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Preview just updated. Wait a moment before trying again.'});
    const [,p,index,target]=data.split(':'),options=Object.keys(PROVIDERS[p]?.options??{}),idx=Number(index);
    if (!options.length || !Number.isInteger(idx)||idx<0) return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Invalid provider.'});
    const row=await store.rewrite(chat,msg.message_id);
    if(hasProtectedLinks(msg.text??'',msg.entities,messageLinks(msg.text??'',msg.entities)))return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'This link is hidden by a spoiler; preview remains disabled.'});
    const candidates=messageLinks(msg.text??'',msg.entities).filter(e=>providerMatches(e.url,PROVIDERS[p]));
    let current;
    if(target) {
      for(const e of candidates) {
        // Older buttons may fingerprint a share token that is now removed.
        if((await hash(linkIdentity(e.url,p))).slice(0,12)===target ||
          (await hash(linkIdentity(e.url,p,false))).slice(0,12)===target){current=e.url;break;}
      }
    } else {
      // Older buttons have no fingerprint: prefer the recorded original post,
      // and only use a fallback when there is exactly one possible link.
      if(row?.original_url) {
        const identity=linkIdentity(row.original_url,p);
        current=candidates.find(e=>linkIdentity(e.url,p)===identity)?.url;
      }
      current??=candidates.length===1?candidates[0].url:undefined;
    }
    if(!current)return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Could not identify the post. Please send the link again.'});
    const health=await store.health();
    const selected=nextHealthy(p,idx,health[p]);
    const selectedIndex=options.indexOf(selected);
    const fixed=fixedFor(current,p,selected);
    const nextTarget=(await hash(linkIdentity(fixed.url,p))).slice(0,12);
    let text=renderLinkedText(msg.text??'',msg.entities,new Map([[current,fixed.url]]));
    const label=row?.sender_name;
    if(label) {
      const attribution=`<i>Shared by <a href="${h(fixed.url)}">${h(label)}</a></i>`;
      const compact=[label,`${PLATFORM_EMOJI[p]??''} ${label}`,`Shared by ${label}`];
      if(compact.includes(msg.text))text=attribution;
      else {
        const footer='\n\nShared by '+label;
        if(msg.text?.endsWith(footer)) {
          const body=msg.text.slice(0,-footer.length);
          text=renderLinkedText(body,(msg.entities??[]).filter(e=>e.offset+e.length<=body.length),new Map([[current,fixed.url]]))+"\n\n"+attribution;
        }
      }
    }
    try {await tg.call('editMessageText',{chat_id:chat,message_id:msg.message_id,text,parse_mode:'HTML',
      link_preview_options:{url:fixed.preview,is_disabled:false,prefer_large_media:true,show_above_text:true},reply_markup:cycleKeyboard(p,(selectedIndex+1)%options.length,nextTarget,selected)});}
    catch(error) {if(!/not modified/i.test(error.message)){if([400,403].includes(error.code))return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Telegram could not update this preview. Try again.'});throw error;}}
    await store.recordLegacyAction(chat,msg.message_id,PROVIDERS[p].noauth_embed?.[selected]??selected);
    ctx.sent=true;
    await tg.call('answerCallbackQuery',{callback_query_id:query.id,text:`Provider: ${selected}`});
    return;
  }
  if (!await tg.admin(chat,query.from?.id,msg.chat.type)) return tg.call('answerCallbackQuery',{callback_query_id:query.id,text:'Only admins can change chat settings.',show_alert:true});
  await tg.call('answerCallbackQuery',{callback_query_id:query.id});
  const state=await store.settings(chat,query.from.id,{includeHealth:false});
  const page=data.startsWith('m:list:')?Number(data.slice(7)):0;
  let text='<b>Choose a platform</b>',keyboard=platformKeyboard(state.choices,page);
  if(data.startsWith('m:p:')) {const p=data.slice(4);if(!PROVIDERS[p])return;text=`<b>${h(platformName(p))}</b>`;keyboard=providerKeyboard(p,state.choices[p]??PROVIDERS[p].default);}
  if(data.startsWith('m:s:')) {const [,,p,k]=data.split(':');if(!PROVIDERS[p]?.options[k])return;await store.choose(chat,p,k);text=`<b>${h(platformName(p))}</b> — ${h(k.toUpperCase())}`;keyboard=providerKeyboard(p,k);}
  await tg.call('editMessageText',{chat_id:chat,message_id:msg.message_id,text,parse_mode:'HTML',reply_markup:keyboard});
}
