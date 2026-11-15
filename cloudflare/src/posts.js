import {PROVIDERS} from './config.js';
import {captureOriginal,entityHTML} from './formatting.js';
import {fixedFor,processText,senderLabel,trim,stripTracking} from './links.js';
import {formatRepost,messageSource,linkIdentity} from './messages.js';
import {quarantined} from './provider-policy.js';
import {hash} from './security.js';

const stamp=()=>Math.floor(Date.now()/1000);
const backend=(p,k)=>PROVIDERS[p]?.noauth_embed?.[k]??k;
const identity=l=>l.platform+':'+linkIdentity(l.url,l.platform);
export async function makePost(msg,result,label,previous=null) {
  const revision=(await hash(JSON.stringify(captureOriginal(msg)))).slice(0,12);
  const links=(result.allLinks??result.links).filter(l=>{try{return ['https:','http:'].includes(new URL(l.url).protocol);}catch{return false;}}).map(l=>({...l,url:trim(l.url)[0],browserKey:Object.hasOwn(PROVIDERS[l.platform]?.noauth_embed??{},l.key)?l.key:previous?.links?.find(old=>old.platform===l.platform&&old.url===trim(l.url)[0])?.browserKey}));
  const tried={};
  for(const l of links)if(l.platform) {
    const key=identity(l),seen=previous?.tried?.[key]??[];
    tried[key]=[...new Set([...seen,l.previewKey??backend(l.platform,l.key)])];
  }
  const old=previous?.links?.[previous.preview_index??0];
  const selected=old?links.findIndex(l=>l.platform===old.platform&&l.url===old.url):-1;
  return {original:captureOriginal(msg),links,label,preview_index:selected>=0?selected:Math.max(0,links.findIndex(l=>l.original===result.links[0]?.original)),tried,revision,edit_date:msg.edit_date??0};
}
export async function postView(post) {
  const original=post.original,text=original.text??original.caption??'',entities=original.entities??original.caption_entities??[];
  if(!post.links.length)return {html:entityHTML(text||'The original message is now empty.',entities),fallback:{text:text||'The original message is now empty.',entities},preview:{is_disabled:true},keyboard:{inline_keyboard:[]}};
  const rendered=formatRepost({text,entities,plainText:text,links:post.links,label:post.label});
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
      keyboard.inline_keyboard.push([{text:'↻ Retry preview',callback_data:`e:${selected.platform}:${(idx+1)%keys.length}:${(await hash(linkIdentity(selected.url,selected.platform))).slice(0,12)}`}]);
    }
  }
  return {...rendered,preview:rendered.protectedLinks?{is_disabled:true}:{is_disabled:false,url:selected.preview??selected.url,prefer_large_media:true,show_above_text:true},keyboard};
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
export async function postCallback(query,store,tg) {
  if(!/^[ep]:/.test(query.data??''))return false;
  const msg=query.message,chat=msg?.chat?.id;
  if(!chat)return false;
  const row=await store.post(chat,msg.message_id);
  if(!row)return false; // Historical buttons continue through the legacy handler.
  const answer=text=>tg.call('answerCallbackQuery',{callback_query_id:query.id,text});
  if(!await store.lockPost(chat,msg.message_id,stamp())){await answer('Another update is in progress. Try again shortly.');return true;}
  try {
    const fresh=await store.post(chat,msg.message_id),post=JSON.parse(fresh.state_json);
    const [kind,arg,target]=query.data.split(':');
    const view=await postView(post);
    if(view.protectedLinks){await answer('This link is hidden by a spoiler; preview remains disabled.');return true;}
    if(kind==='p') {
      if(target!==post.revision||!/^\d+$/.test(arg)||!post.links[Number(arg)]){await answer('This preview choice is outdated. Use the latest buttons.');return true;}
      if(query.from?.id!==fresh.user_id&&!await tg.admin(chat,query.from?.id,msg.chat.type)){await answer('Only the original sender or a chat admin can choose the preview.');return true;}
      if(post.preview_index===Number(arg)){await answer('This link is already selected.');return true;}
      post.preview_index=Number(arg);
      sanitisePost(post);
    } else {
      const link=post.links[post.preview_index??0],p=arg;
      const fingerprint=query.data.split(':')[3];
      if(!link?.platform||link.platform!==p||(fingerprint&&(await hash(linkIdentity(link.url,p))).slice(0,12)!==fingerprint&&(await hash(linkIdentity(link.url,p,false))).slice(0,12)!==fingerprint)) {
        await answer('This retry button is outdated. Use the latest buttons.');return true;
      }
      const cleaned=sanitisePost(post);
      const state=await store.settings(chat,query.from?.id??0),keys=Object.keys(PROVIDERS[p].options);
      const tried=post.tried[identity(link)]??[],idx=keys.indexOf(link.key);
      let selected;
      for(let n=1;n<=keys.length;n++) {
        const key=keys[(idx+n)%keys.length],effective=backend(p,key);
        if(!tried.includes(effective)&&!quarantined(state.health[p]?.[effective])){selected=key;break;}
      }
      if(!selected){
        if(cleaned){await editPost(tg,chat,msg.message_id,await postView(post));await store.savePost(chat,msg.message_id,fresh.source_msg_id,fresh.user_id,post,fresh.ts);}
        await answer((cleaned?'Tracking removed. ':'')+'All available preview providers have been tried. No alternatives remain for this post.');return true;
      }
      const fixed=fixedFor(link.url,p,selected);
      // Preserve an explicitly chosen browser frontend while changing only its preview.
      if(!link.browserKey)link.url=fixed.url;
      link.preview=fixed.preview;link.previewKey=backend(p,selected);link.key=selected;
      post.tried[identity(link)]=[...new Set([...tried,link.previewKey])];
    }
    const updated=await postView(post);
    await answer(kind==='p'?`Preview: link ${post.preview_index+1}`:`Provider: ${post.links[post.preview_index].previewKey}`);
    await editPost(tg,chat,msg.message_id,updated);
    await store.savePost(chat,msg.message_id,fresh.source_msg_id,fresh.user_id,post,fresh.ts);
    const active=post.links[post.preview_index];
    await store.updateProvider(chat,msg.message_id,active?.previewKey??null);
    return true;
  } finally {await store.unlockPost(chat,msg.message_id);}
}
export async function syncEdit(msg,row,store,tg,state,ctx) {
  if(row.user_id!==(msg.from?.id??0))return;
  if(!await store.lockPost(msg.chat.id,row.bot_msg_id,stamp()))throw new Error('Post edit is busy');
  try {
    const fresh=await store.post(msg.chat.id,row.bot_msg_id),previous=JSON.parse(fresh.state_json);
    if((msg.edit_date??0)<(previous.edit_date??0))return;
    const result=await processText(messageSource(msg).trim(),state.settings,state.choices,state.overrides,fetch,false,state.health);
    if(result.tooMany)return; // Keep the original and existing repost on oversized edits.
    // Reuse a manually selected backend for a post whose identity survives the edit.
    for(const link of result.allLinks??result.links) {
      const old=previous.links.find(l=>l.platform===link.platform&&l.url===trim(link.url)[0]);
      if(old&&link.platform&&!quarantined(state.health[link.platform]?.[old.previewKey])){const fixed=fixedFor(link.url,link.platform,old.key);link.preview=fixed.preview;link.key=old.key;link.previewKey=old.previewKey;}
    }
    const post=await makePost(msg,result,senderLabel(msg.from,state.settings.sender_mode),previous),view=await postView(post);
    if(post.revision===previous.revision){previous.edit_date=Math.max(previous.edit_date??0,msg.edit_date??0);await store.savePost(msg.chat.id,row.bot_msg_id,msg.message_id,row.user_id,previous,fresh.ts);return;}
    if((view.fallback?.text.length??0)>4096)return;
    await editPost(tg,msg.chat.id,row.bot_msg_id,view);ctx.sent=true;
    await store.refreshOriginal(msg.chat.id,row.bot_msg_id,post);
    await store.savePost(msg.chat.id,row.bot_msg_id,msg.message_id,row.user_id,post,fresh.ts);
  } finally {await store.unlockPost(msg.chat.id,row.bot_msg_id);}
}
