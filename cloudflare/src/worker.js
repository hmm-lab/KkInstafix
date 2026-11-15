import {InvocationBudget,BudgetedDB,BudgetError} from './budget.js';
import {JsonCache} from './cache.js';
import {VERSION} from './version.js';
import {makePost,postView,syncEdit} from './posts.js';
import {PROVIDERS,PROVIDER_REVISION} from './config.js';
import {processText,urls,trim,senderLabel,escapeHTML as h} from './links.js';
import {captureOriginal} from './formatting.js';
import {runHealthChecks} from './health.js';
import {messageSource,formatRepost} from './messages.js';
import {Store,DEFAULTS} from './store.js';
import {Telegram,TelegramError} from './telegram.js';
import {command,callback} from './commands.js';
import {readBounded,matchesSecret,hash,seal,unseal} from './security.js';
import {SETUP_HTML} from './setup.js';

const headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff',
  'Content-Security-Policy':"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"};
const json=(body,status=200,extra={})=>Response.json(body,{status,headers:{...headers,...extra}});
const now=()=>Math.floor(Date.now()/1000);
async function activate(request,env,store) {
  if (!await matchesSecret((request.headers.get('Authorization')??'').replace(/^Bearer /,''),env.SETUP_HASH)) return json({error:'Invalid private setup link.'},403);
  const existing=await store.stmt('SELECT activated FROM runtime_config WHERE id=1').first();
  if (existing?.activated) return json({error:'This bot is already activated. Setup is closed.'},409);
  let input;
  try {input=JSON.parse(new TextDecoder().decode(await readBounded(request.body,4096)));} catch {return json({error:'Invalid setup request.'},400);}
  if (!/^\d+:[A-Za-z0-9_-]{20,100}$/.test(input.token??'')) return json({error:'That does not look like a Telegram bot token.'},400);
  const tg=new Telegram(input.token,env.REQUEST_FETCH??fetch);
  let me;
  try {me=await tg.call('getMe');} catch {return json({error:'Telegram could not verify that token. Check it in @BotFather and try again.'},400);}
  if (!me.is_bot||!me.username) return json({error:'The token must belong to a Telegram bot.'},400);
  const cipher=await seal(input.token,env.CONFIG_KEY);
  // Reserve setup atomically. A failed connection keeps the encrypted token so
  // the private setup link can safely be retried; it never appears in logs.
  const reserved=await store.stmt(`INSERT INTO runtime_config VALUES(1,?,?,?,0)
    ON CONFLICT(id) DO UPDATE SET token_cipher=excluded.token_cipher,bot_id=excluded.bot_id,username=excluded.username
    WHERE runtime_config.activated=0 RETURNING id`,cipher,me.id,me.username).first();
  if(!reserved)return json({error:'Setup has already completed.'},409);
  try {
    await tg.call('setWebhook',{url:env.WEBHOOK_URL,secret_token:env.WEBHOOK_SECRET,drop_pending_updates:false,
      allowed_updates:['message','edited_message','channel_post','edited_channel_post','callback_query','inline_query'],max_connections:1});
    await store.stmt('UPDATE runtime_config SET activated=1 WHERE id=1').run();
    // Do not alter group membership or drop pending messages during migration.
    return json({ok:true,username:me.username});
  } catch {return json({error:'Token verified, but Telegram could not connect the webhook. Try activating again.'},502);}
}
async function inline(query,tg,store) {
  const source=query.query??'';
  if(!urls(source).length)return tg.call('answerInlineQuery',{inline_query_id:query.id,cache_time:1,is_personal:true,results:[{type:'article',id:'hint',title:'Paste a social link',input_message_content:{message_text:'Paste a link after the bot username.'}}]});
  const result=await processText(source,DEFAULTS,{},{},tg.net,false,await store.health(),store.cache);
  if(result.tooMany)return tg.call('answerInlineQuery',{inline_query_id:query.id,cache_time:1,is_personal:true,results:[{type:'article',id:'limit',title:'Use up to 8 links per message',input_message_content:{message_text:'Use up to 8 links per inline message, then try again.',link_preview_options:{is_disabled:true}}}]});
  const first=result.links[0];
  const link=first?.url??urls(source)[0];
  // Inline mode keeps the entire query, not just its first URL.
  if(result.text.length>4096)return tg.call('answerInlineQuery',{inline_query_id:query.id,cache_time:1,is_personal:true,results:[{type:'article',id:'too-long',title:'Message is too long — shorten it first',input_message_content:{message_text:'This message exceeds Telegram’s limit. Shorten it and try again.',link_preview_options:{is_disabled:true}}}]});
  const previews=(result.allLinks??result.links).filter(candidate=>{try{return ['http:','https:'].includes(new URL(candidate.url).protocol);}catch{return false;}});
  if(!previews.length)previews.push({url:link,preview:link});
  return tg.call('answerInlineQuery',{inline_query_id:query.id,cache_time:10,is_personal:true,results:previews.map((candidate,index)=>({
    type:'article',id:index===0?'fixed':`fixed-${index}`,title:previews.length>1?`Preview ${index+1} · ${candidate.platform??new URL(candidate.url).hostname}`:first?'Fixed links':'Clean links',description:candidate.url,
    input_message_content:{message_text:result.text,link_preview_options:{is_disabled:false,url:candidate.preview??candidate.url,show_above_text:true,prefer_large_media:true}},
  }))});
}
async function rewrite(msg,update,store,tg,ctx) {
  const chat=msg.chat.id,user=msg.from?.id??0,stamp=now(),text=messageSource(msg).trim();
  if(msg.from?.is_bot)return;
  const state=await store.settings(chat,user,{includeHealth:urls(text).length>0||/^\/(providers|preview|clean)(?:@|\s|$)/i.test(text)});
  if(state.muted) {await tg.remove(chat,msg.message_id);return;}
  if(text.startsWith('/')) {await command(msg,store,tg,state,ctx);return;}
  const settings=state.settings;
  if(!settings.enabled||state.optout||(settings.ignore_forwards&&msg.forward_origin))return;
  if(update.edited_message||update.edited_channel_post) {
    const previous=await store.sourcePost(chat,msg.message_id);
    if(previous){await syncEdit(msg,previous,store,tg,state,ctx);return;}
  }
  if(!urls(text).length) {
    if(settings.text_spam&&text.length>=4 && !await store.claimRecent('text',chat,text.toLowerCase(),settings.dedup_window,stamp)) await tg.remove(chat,msg.message_id);
    if(msg.sticker||msg.animation) {
      const id=msg.sticker?.file_unique_id??msg.animation?.file_unique_id;
      if(id&&!await store.claimRecent('media',chat,id,settings.dedup_window,stamp))await tg.remove(chat,msg.message_id);
    }
    return;
  }
  const result=await processText(text,settings,state.choices,state.overrides,tg.net,false,state.health,store.cache);
  if(result.tooMany||!result.links.length)return;
  if(!await store.rate(chat,user,update.update_id,settings.rate_limit,settings.rate_window,stamp)) {
    if(await store.claimRecent('ratewarn',chat,String(user),settings.rate_window,stamp)) await tg.send(chat,'⏱ Slow down — link rate limit reached.');
    return;
  }
  const reservations=[];
  let sent=false;
  try {
    for(const link of result.links) {
      const key=await hash(link.raw??link.original);
      if(await store.claimRecent('fix',chat,key,settings.dedup_window,stamp))reservations.push({...link,eventKey:key});
    }
    if(!reservations.length)return;
    const first=result.links[0],label=senderLabel(msg.from,settings.sender_mode);
    let {html,plain,fallback,protectedLinks}=formatRepost({text:msg.text??msg.caption??'',
      entities:msg.text!==undefined?msg.entities:msg.caption_entities,
      plainText:result.text,links:result.links,label});
    const post=await makePost(msg,result,label),view=await postView(post,{html,plain,fallback,protectedLinks});
    const preview=protectedLinks?{is_disabled:true}:first.preview?{is_disabled:false,url:first.preview,prefer_large_media:true,show_above_text:true}:undefined;
    let keyboard=view.keyboard.inline_keyboard.length?view.keyboard:undefined;
    // A companion reply preserves the full original when expansion exceeds
    // Telegram's limit. Very long URLs use short clickable labels instead.
    const companion=plain.length>4096;
    if(companion) {
      fallback=undefined;
      // A long spoiler must never be exposed in a plain companion reply.
      if(protectedLinks) {
        if(await store.claimRecent('formatwarn',chat,String(user),60,stamp)) {
          await tg.send(chat,'This formatted message is too long to replace safely. Your original message was kept.',
            {link_preview_options:{is_disabled:true},message_thread_id:msg.message_thread_id,
              reply_parameters:{message_id:msg.message_id,allow_sending_without_reply:true}});
          ctx.sent=true;
        }
        return;
      }
      plain=result.links.map(link=>link.url).join('\n');
      if(plain.length>4096) {
        html=result.links.map((link,i)=>`<a href="${h(trim(link.url)[0])}">Open fixed link ${i+1}</a>`).join('\n');
        plain='The rewritten link is too long for Telegram. Your original message was kept; try a shorter link.';
      } else html=h(plain);
    }
    const replyId=companion||msg.caption||update.edited_message||update.edited_channel_post?msg.message_id:msg.reply_to_message?.message_id;
    await store.finishUpdate(update.update_id,'sending',stamp);
    const delivered=await tg.deliver(chat,html,plain,{link_preview_options:preview,reply_markup:keyboard,
      fallback_message:fallback,message_thread_id:msg.message_thread_id,reply_parameters:replyId?{message_id:replyId,allow_sending_without_reply:true}:undefined});
    sent=true;ctx.sent=true;
    // Persist recoverable content before deletion; storage errors keep originals.
    await store.record(chat,delivered.message_id,first.raw??first.original,label,
      reservations.map(r=>r.platform).filter(Boolean),user,stamp,
      {original:captureOriginal(msg),platform:first.platform,provider:first.previewKey??first.key,post:companion?null:post,source_id:msg.message_id});
    if(update.message?.text&&!companion) await tg.remove(chat,msg.message_id);
  } finally {
    if(!sent) {
      for(const r of reservations)await store.releaseRecent('fix',chat,r.eventKey,stamp);
      await store.stmt('DELETE FROM rate_events WHERE chat_id=? AND user_id=? AND event_id=?',chat,user,update.update_id).run();
    }
  }
}
const worker = {
  async fetch(request,env) {
    const url=new URL(request.url),store=new Store(env.DB,new JsonCache(caches.default,undefined,undefined,env.INVOCATION_BUDGET));
    if(request.method==='GET'&&url.pathname==='/setup')return new Response(SETUP_HTML,{headers:{...headers,'Content-Type':'text/html;charset=utf-8'}});
    if(request.method==='GET'&&['/','/health'].includes(url.pathname)) {
      const row=await store.stmt('SELECT username,activated FROM runtime_config WHERE id=1').first();
      return json({service:'KkInstafix',version:VERSION,hosting:'Cloudflare Workers + D1',providers_updated:PROVIDER_REVISION,provider_options:Object.values(PROVIDERS).reduce((n,p)=>n+Object.keys(p.options).length,0),active:!!row?.activated,bot:row?.activated?row.username:undefined});
    }
    if(request.method==='POST'&&url.pathname==='/setup') {
      try{return await activate(request,env,store);}catch{console.error(JSON.stringify({event:'setup_error'}));return json({error:'Setup could not complete. Try again.'},500);}
    }
    if(request.method==='POST'&&url.pathname==='/admin/check-providers') {
      if(!await matchesSecret((request.headers.get('Authorization')??'').replace(/^Bearer /,''),env.SETUP_HASH))return json({error:'Forbidden'},403);
      return json(await runHealthChecks(store,{stamp:now(),net:env.REQUEST_FETCH??fetch,batchSize:2}));
    }
    if(request.method==='POST'&&url.pathname==='/admin/status') {
      if(!await matchesSecret((request.headers.get('Authorization')??'').replace(/^Bearer /,''),env.SETUP_HASH))return json({error:'Forbidden'},403);
      const config=await store.stmt('SELECT * FROM runtime_config WHERE id=1').first();
      if(!config?.activated)return json({active:false});
      try {
        const tg=new Telegram(await unseal(config.token_cipher,env.CONFIG_KEY),env.REQUEST_FETCH??fetch);
        const [info,me]=await Promise.all([tg.call('getWebhookInfo'),tg.call('getMe')]);
        const health=await store.health();
        const healthRows=Object.values(health).flatMap(p=>Object.values(p));
        return json({active:true,free_tier:env.INVOCATION_BUDGET?.snapshot(),provider_health:{checked:healthRows.length,temporarily_skipped:healthRows.filter(r=>r.cooldown_until>now()).length,last_check:Math.max(0,...healthRows.map(r=>r.checked_at))},bot:{id:me.id,username:me.username,can_read_all_group_messages:me.can_read_all_group_messages,
          supports_inline_queries:me.supports_inline_queries},webhook:{
          url:(info.url??'').replace(/\d+:[A-Za-z0-9_-]+/g,'[redacted]'),pending_update_count:info.pending_update_count,
          last_error_date:info.last_error_date,last_error_message:info.last_error_message,
          max_connections:info.max_connections,allowed_updates:info.allowed_updates},expected_webhook:env.WEBHOOK_URL});
      } catch(error) {return json({error:'Telegram status unavailable',code:error.code??null},502);}
    }
    if(url.pathname!=='/webhook'||request.method!=='POST')return json({error:'Not found'},404);
    if(!await matchesSecret(request.headers.get('X-Telegram-Bot-Api-Secret-Token')??'',await hash(env.WEBHOOK_SECRET)))return json({error:'Forbidden'},403);
    const config=await store.stmt('SELECT * FROM runtime_config WHERE id=1').first();
    if(!config?.activated)return json({error:'Bot not activated'},503);
    let update;
    try {update=JSON.parse(new TextDecoder().decode(await readBounded(request.body)));} catch{return json({error:'Invalid update'},400);}
    if(!Number.isSafeInteger(update.update_id))return json({error:'Missing update ID'},400);
    const claim=await store.claimUpdate(update.update_id,now());
    if(claim==='busy')return json({error:'Update is still processing'},503,{'Retry-After':'5'});
    if(claim==='duplicate')return json({ok:true,duplicate:true});
    const ctx={sent:false,operation_id:'update:'+update.update_id};
    try {
      const tg=new Telegram(await unseal(config.token_cipher,env.CONFIG_KEY),env.REQUEST_FETCH??fetch);
      tg.username=config.username;
      if(update.inline_query)await inline(update.inline_query,tg,store);
      else if(update.callback_query)await callback(update.callback_query,store,tg,ctx);
      else {
        const msg=update.message??update.edited_message??update.channel_post??update.edited_channel_post;
        if(msg?.chat)await rewrite(msg,update,store,tg,ctx);
      }
      await store.finishUpdate(update.update_id,'done',now());
      return json({ok:true});
    } catch(error) {
      const code=error instanceof TelegramError?error.code:null;
      console.error(JSON.stringify({event:'update_failed',update_id:update.update_id,telegram_code:code,delivered:ctx.sent}));
      if(ctx.sent||[0,400,403].includes(code)) {
        // A transport timeout has an ambiguous outcome: leave the original and
        // acknowledge to avoid duplicate sends. Users can retry with a new post.
        await store.finishUpdate(update.update_id,ctx.sent?'delivered':'rejected',now());
        return json({ok:true});
      }
      await store.stmt('DELETE FROM deliveries WHERE update_id=?',update.update_id).run();
      return json({error:'Temporarily unavailable'},503,code===429?{'Retry-After':String(error.retryAfter??30)}:{});
    }
  },
  async scheduled(_event,env) {const store=new Store(env.DB,new JsonCache(caches.default,undefined,undefined,env.INVOCATION_BUDGET));await store.cleanup(now());await runHealthChecks(store,{stamp:now(),net:env.REQUEST_FETCH??fetch,batchSize:2});},
};

export default {
  async fetch(request,env) {
    const budget=new InvocationBudget(),db=new BudgetedDB(env.DB,budget),protectedRequest=request.method==='POST';
    if(protectedRequest&&!await budget.admit(env.DB)&&new URL(request.url).pathname!=='/admin/status')return json({ok:true,paused:true,reason:'Bot free-tier safety allowance reached; originals are left unchanged until the next UTC day.'});
    try {return await worker.fetch(request,{...env,DB:db,INVOCATION_BUDGET:budget,REQUEST_FETCH:budget.network(fetch)});}
    catch(error){if(error instanceof BudgetError)return json({error:'Free-tier request budget reached. Original messages are preserved.'},503,{'Retry-After':'60'});throw error;}
    finally {if(protectedRequest)try{await budget.persist(env.DB);}catch{console.error(JSON.stringify({event:'usage_accounting_unavailable'}));}}
  },
  async scheduled(event,env) {
    const budget=new InvocationBudget();if(!await budget.admit(env.DB,true))return;
    try {await worker.scheduled(event,{...env,DB:new BudgetedDB(env.DB,budget),INVOCATION_BUDGET:budget,REQUEST_FETCH:budget.network(fetch)});}
    finally{await budget.persist(env.DB);}
  },
};
