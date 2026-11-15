import {probeURL} from './health.js';
import {PROVIDERS} from './config.js';
import {captureOriginal,entityHTML,hasProtectedLinks} from './formatting.js';
import {fixedFor,processText,senderLabel,trim,stripTracking} from './links.js';
import {formatRepost,messageSource,messageLinks,linkIdentity} from './messages.js';
import {quarantined} from './provider-policy.js';
import {hash} from './security.js';

const stamp=()=>Math.floor(Date.now()/1000);
const backend=(p,k)=>PROVIDERS[p]?.noauth_embed?.[k]??k;
const identity=l=>l.platform+':'+linkIdentity(l.url,l.platform);
export async function makePost(msg,result,label,previous=null,appearance={}) {
  const revision=(await hash(JSON.stringify(captureOriginal(msg)))).slice(0,12);
  const links=(result.allLinks??result.links).filter(l=>{try{return ['https:','http:'].includes(new URL(l.url).protocol);}catch{return false;}}).map(l=>({...l,url:trim(l.url)[0],browserKey:Object.hasOwn(PROVIDERS[l.platform]?.noauth_embed??{},l.key)?l.key:previous?.links?.find(old=>old.platform===l.platform&&old.url===trim(l.url)[0])?.browserKey}));
  const tried={};
  for(const l of links)if(l.platform) {
    const key=identity(l),seen=previous?.tried?.[key]??[];
    tried[key]=[...new Set([...seen,l.previewKey??backend(l.platform,l.key)])];
  }
  const old=previous?.links?.[previous.preview_index??0];
  const selected=old?links.findIndex(l=>l.platform===old.platform&&l.url===old.url):-1;
  return {original:captureOriginal(msg),links,label,preview_size:appearance.preview_size??previous?.preview_size??'large',preview_index:selected>=0?selected:Math.max(0,links.findIndex(l=>l.original===result.links[0]?.original)),tried,revision,edit_date:msg.edit_date??0};
}
export async function postView(post,existingRender=null) {
  const original=post.original,text=original.text??original.caption??'',entities=original.entities??original.caption_entities??[];
  if(!post.links.length)return {html:entityHTML(text||'The original message is now empty.',entities),fallback:{text:text||'The original message is now empty.',entities},preview:{is_disabled:true},keyboard:{inline_keyboard:[]}};
  const rendered=existingRender??formatRepost({text,entities,plainText:text,links:post.links,label:post.label});
  const selected=post.links[post.preview_index??0]??post.links[0];
  const keyboard={inline_keyboard:[]};
  if(!rendered.protectedLinks) {
    if(post.links.length>1) {
      for(let i=0;i<post.links.length;i+=2)keyboard.inline_keyboard.push(post.links.slice(i,i+2).map((link,j)=>({
        text:`${i+j===post.preview_index?'✓ ':''}${i+j+1} · ${link.platform??new URL(link.url).hostname}`,
        callback_data:`p:${i+j}:${post.revision}`,
      })));
    }
    if(selected.platform&&Object.keys(PROVIDERS[selected.platform].options).length>1) {
      const keys=Object.keys(PROVIDERS[selected.platform].options),idx=keys.indexOf(selected.key);
      const backends=keys.filter(k=>!Object.hasOwn(PROVIDERS[selected.platform].noauth_embed??{},k));
      const active=selected.previewKey??backend(selected.platform,selected.key);
      keyboard.inline_keyboard.push([{text:`↻ Retry · ${active==='native'?'Native':active.toUpperCase()} · ${Math.max(0,backends.indexOf(active))+1}/${backends.length}`,callback_data:`e:${selected.platform}:${(idx+1)%keys.length}:${(await hash(linkIdentity(selected.url,selected.platform))).slice(0,12)}`}]);
    }
  }
  return {...rendered,preview:rendered.protectedLinks?{is_disabled:true}:{is_disabled:false,url:selected.preview??selected.url,prefer_large_media:post.preview_size!=='compact',prefer_small_media:post.preview_size==='compact',show_above_text:true},keyboard};
}
export async function editPost(tg,chat,id,view) {
  const base={chat_id:chat,message_id:id,link_preview_options:view.preview,reply_markup:view.keyboard};
  try {await tg.call('editMessageText',{...base,text:view.html,parse_mode:'HTML'});}
  catch(error) {
    if(/not modified/i.test(error.message))return;
    if(error.code!==400||!view.fallback)throw error;
    // Preserve entities (especially spoilers) if HTML fails. Never send a new post.
    try {await tg.call('editMessageText',{...base,...view.fallback});}
    catch(second){if(!/not modified/i.test(second.message))throw second;}
  }
}
// Reapply current cleanup policy to persisted links without changing undo data.
export function sanitisePost(post) {
  let changed=false;
  for(const link of post.links) {
    const oldKey=link.platform?link.platform+':'+linkIdentity(link.url,link.platform,false):null;
    const url=stripTracking(link.url,link.platform),preview=link.preview?stripTracking(link.preview,link.platform):link.preview;
    changed ||= url!==link.url||preview!==link.preview;
    link.url=url;link.preview=preview;
    if(oldKey&&oldKey!==identity(link)) {
      post.tried[identity(link)]=[...new Set([...(post.tried[identity(link)]??[]),...(post.tried[oldKey]??[])])];
      delete post.tried[oldKey];
    }
  }
  return changed;
}
async function answerAction(query,tg,text) {
  try {
    if(query.id)await tg.call('answerCallbackQuery',{callback_query_id:query.id,text});
    else await tg.send(query.message.chat.id,text,{reply_parameters:{message_id:query.command_id,allow_sending_without_reply:true},message_thread_id:query.message.message_thread_id});
  }catch{console.warn(JSON.stringify({event:'preview_notice_unavailable'}));}
}
export async function applyOperation(op,store,tg,ctx={}) {
  if(op.state==='done'){ctx.sent=true;return JSON.parse(op.desired_json);}
  const post=JSON.parse(op.desired_json);
  try {await editPost(tg,op.chat_id,op.bot_msg_id,await postView(post));}
  catch(error) {
    if([400,403].includes(error.code))await store.failOperation(op.operation_id);
    // Edits are idempotent: safely replay the frozen desired state after an ambiguous timeout.
    if(error.code===0)throw new Error('Preview edit outcome needs reconciliation');
    throw error;
  }
  await store.commitOperation(op);ctx.sent=true;
  return post;
}
export async function postCallback(query,store,tg,ctx={}) {
  if(!/^[epra]:/.test(query.data??''))return false;
  const msg=query.message,chat=msg?.chat?.id;
  if(!chat)return false;
  const row=await store.post(chat,msg.message_id);
  if(!row)return false;
  const answer=text=>answerAction(query,tg,text),opid=query.id?'callback:'+query.id:ctx.operation_id;
  if(!opid)throw new Error('Missing preview operation identity');
  const existing=await store.operation(opid);
  if(!existing&&!await store.tapAllowed(chat,msg.message_id)){await answer('Preview just updated. Wait a moment before trying again.');return true;}
  if(!await store.lockPost(chat,msg.message_id,stamp())){
    if(existing?.state==='pending')throw new Error('Preview recovery is busy');
    await answer('Another update is in progress. Try again shortly.');return true;
  }
  try {
    if(existing?.state==='failed'){await answer('Telegram could not update this preview. Try again or send the link again.');return true;}
    if(existing) {
      const recovered=await applyOperation(existing,store,tg,ctx);
      await answer(`Provider: ${recovered.links[recovered.preview_index]?.previewKey??'original'}`);return true;
    }
    const pending=await store.pendingOperation(chat,msg.message_id);
    if(pending){await applyOperation(pending,store,tg,ctx);await answer('Previous preview update recovered. Tap again to continue.');return true;}
    const fresh=await store.post(chat,msg.message_id);
    if(!fresh){await answer('These controls have expired. Send the link again.');return true;}
    const post=JSON.parse(fresh.state_json),[kind,arg,target]=query.data.split(':');
    const original=post.original,text=original.text??original.caption??'',entities=original.entities??original.caption_entities??[];
    if(hasProtectedLinks(text,entities,messageLinks(text,entities))){await answer('This link is hidden by a spoiler; preview remains disabled.');return true;}
    if(kind==='p') {
      if(target!==post.revision||!/^\d+$/.test(arg)||!post.links[Number(arg)]){await answer('This preview choice is outdated. Use the latest buttons.');return true;}
      if(query.from?.id!==fresh.user_id&&!await tg.admin(chat,query.from?.id,msg.chat.type)){await answer('Only the original sender or a chat admin can choose the preview.');return true;}
      if(post.preview_index===Number(arg)){await answer('This link is already selected.');return true;}
      post.preview_index=Number(arg);sanitisePost(post);
    } else if(kind==='a') {
      const link=post.links[post.preview_index??0];
      if(!link?.platform){await answer('This link has no alternative preview providers.');return true;}
      if(!await store.claimRecent('repair',chat,String(query.from?.id??0),30,stamp())){await answer('Wait 30 seconds before another repair in this chat.');return true;}
      sanitisePost(post);
      const p=link.platform,health=await store.health(),keys=Object.keys(PROVIDERS[p].options),idx=keys.indexOf(link.key);
      let selected=null,fixed=null;
      // At most three alternatives / six fetches; no media download or global health change.
      const candidates=Array.from({length:keys.length},(_,i)=>keys[(idx+i+1)%keys.length]).filter(k=>k!==(link.previewKey??backend(p,link.key))&&!Object.hasOwn(PROVIDERS[p].noauth_embed??{},k)&&!quarantined(health[p]?.[k])).slice(0,3);
      if(!candidates.length){await answer('No alternative provider is available. Use /refresh to request the current preview again.');return true;}
      for(const key of candidates){const candidate=fixedFor(link.url,p,key);if((await probeURL(candidate.preview,tg.net)).kind==='success'){selected=key;fixed=candidate;break;}}
      if(!fixed){await answer('Could not verify an alternative preview. The current post was kept; a blocked or slow response does not mean a provider is broken.');return true;}
      if(!link.browserKey)link.url=fixed.url;
      link.key=selected;link.previewKey=selected;link.preview=fixed.preview;
      post.tried[identity(link)]=[...new Set([...(post.tried[identity(link)]??[]),selected])];
    } else if(kind==='r') {
      sanitisePost(post);const link=post.links[post.preview_index];
      if(!link){await answer('No link is available to refresh.');return true;}
      const preview=new URL(link.preview??link.url);preview.searchParams.set('_kk_refresh',(await hash(opid)).slice(0,12));link.preview=preview.href;
    } else {
      const link=post.links[post.preview_index??0],p=arg,fingerprint=query.data.split(':')[3];
      if(!link?.platform||link.platform!==p||(fingerprint&&(await hash(linkIdentity(link.url,p))).slice(0,12)!==fingerprint&&(await hash(linkIdentity(link.url,p,false))).slice(0,12)!==fingerprint)) {
        await answer('This retry button is outdated. Use the latest buttons.');return true;
      }
      const cleaned=sanitisePost(post),health=await store.health(),keys=Object.keys(PROVIDERS[p].options);
      let tried=post.tried[identity(link)]??[];const idx=keys.indexOf(link.key);
      const next=()=>{for(let n=1;n<=keys.length;n++){const key=keys[(idx+n)%keys.length],effective=backend(p,key);
        if(Object.hasOwn(PROVIDERS[p].noauth_embed??{},key))continue;
        if(!tried.includes(effective)&&!quarantined(health[p]?.[effective]))return key;
      }};
      let selected=next();if(!selected){tried=[];selected=next();}
      if(!selected){
        if(cleaned)await applyOperation(await store.prepareOperation(opid,chat,msg.message_id,post,'callback'),store,tg,ctx);
        await answer((cleaned?'Tracking removed. ':'')+'Preview providers are temporarily unavailable. Try again later.');return true;
      }
      const fixed=fixedFor(link.url,p,selected);
      if(!link.browserKey)link.url=fixed.url;
      link.preview=fixed.preview;link.previewKey=backend(p,selected);link.key=selected;
      post.tried[identity(link)]=[...new Set([...tried,link.previewKey])];
    }
    const op=await store.prepareOperation(opid,chat,msg.message_id,post,'callback');
    await applyOperation(op,store,tg,ctx);
    await answer(kind==='a'?'Preview repaired using verified metadata. Playback still depends on Telegram.':kind==='r'?'Preview refresh requested. Telegram may reuse its cached preview.':kind==='p'?`Preview: link ${post.preview_index+1}`:`Provider: ${post.links[post.preview_index].previewKey}`);
    return true;
  } catch(error) {
    if([400,403].includes(error.code)){await answer('Telegram could not update this preview. Try again or send the link again.');return true;}
    throw error;
  } finally {await store.unlockPost(chat,msg.message_id);}
}
async function editLimitNotice(msg,store,tg,reason,ctx) {
  if(await store.claimRecent('editwarn',msg.chat.id,String(msg.from?.id??0),60,stamp())) {
    await tg.send(msg.chat.id,reason+' The existing preview was kept. Shorten the original message and edit it again.',
      {message_thread_id:msg.message_thread_id,link_preview_options:{is_disabled:true},reply_parameters:{message_id:msg.message_id,allow_sending_without_reply:true}});
    ctx.sent=true;
  }
}
export async function syncEdit(msg,row,store,tg,state,ctx) {
  if(row.user_id!==(msg.from?.id??0))return;
  if(!await store.lockPost(msg.chat.id,row.bot_msg_id,stamp()))throw new Error('Post edit is busy');
  try {
    const existing=await store.operation(ctx.operation_id);
    if(existing){if(existing.state!=='failed')await applyOperation(existing,store,tg,ctx);return;}
    const pending=await store.pendingOperation(msg.chat.id,row.bot_msg_id);
    if(pending)await applyOperation(pending,store,tg,{});
    const fresh=await store.post(msg.chat.id,row.bot_msg_id);if(!fresh)return;
    const previous=JSON.parse(fresh.state_json);
    if((msg.edit_date??0)<(previous.edit_date??0))return;
    const result=await processText(messageSource(msg).trim(),state.settings,state.choices,state.overrides,tg.net,false,state.health,store.cache);
    if(result.tooMany)return editLimitNotice(msg,store,tg,'This edit contains more than eight links.',ctx);
    for(const link of result.allLinks??result.links) {
      const old=previous.links.find(l=>l.platform===link.platform&&l.url===trim(link.url)[0]);
      if(old&&link.platform&&!quarantined(state.health[link.platform]?.[old.previewKey])){const fixed=fixedFor(link.url,link.platform,old.key);link.preview=fixed.preview;link.key=old.key;link.previewKey=old.previewKey;}
    }
    const post=await makePost(msg,result,state.settings.attribution===0?'':senderLabel(msg.from,state.settings.sender_mode),previous,state.settings),view=await postView(post);
    if(post.revision===previous.revision){previous.edit_date=Math.max(previous.edit_date??0,msg.edit_date??0);await store.savePost(msg.chat.id,row.bot_msg_id,msg.message_id,row.user_id,previous,fresh.ts);return;}
    if((view.fallback?.text.length??0)>4096)return editLimitNotice(msg,store,tg,'This edit exceeds Telegram’s message limit.',ctx);
    await applyOperation(await store.prepareOperation(ctx.operation_id,msg.chat.id,row.bot_msg_id,post,'source'),store,tg,ctx);
  } finally {await store.unlockPost(msg.chat.id,row.bot_msg_id);}
}
