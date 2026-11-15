import {test,after,before} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {Miniflare} from 'miniflare';
import {fixLink,processText,stripTracking,platformFor} from '../src/links.js';
import {PROVIDERS} from '../src/config.js';
import {Store} from '../src/store.js';
import {entityHTML,rewriteEntities,captureOriginal} from '../src/formatting.js';
import {runHealthChecks,probeURL,usableMetadata,probePlan,CONTENT_SAMPLES,OBSERVATION_SAMPLES} from '../src/health.js';
import {pickHealthy,quarantined} from '../src/provider-policy.js';
import {diagnosticURL} from '../src/diagnostics.js';
import {messageSource,formatRepost} from '../src/messages.js';
import {permissionStatus} from '../src/status.js';
import {Telegram,TelegramError} from '../src/telegram.js';

const bootstrap='private-test-setup-key-32-characters';
const hash=s=>createHash('sha256').update(s).digest('hex');
const token='123456:abcdefghijklmnopqrstuvwxyz123456789';
const calls=[];let failure=null,editFailure=null,deleteFail=false,backup={};
const mf=new Miniflare({modules:true,scriptPath:new URL('../dist/worker.js',import.meta.url).pathname,
  // The installed workerd binary supports compatibility through 2026-08-06.
  compatibilityDate:'2026-08-06',d1Databases:{DB:'kkinstafix-test'},
  bindings:{CONFIG_KEY:'a1'.repeat(32),SETUP_HASH:hash(bootstrap),WEBHOOK_SECRET:'webhook-test-secret',WEBHOOK_URL:'https://bot.example/webhook'},
  outboundService:async request=>{
    const url=new URL(request.url);
    assert.equal(url.host,'api.telegram.org','tests must not make external provider requests');
    if(url.pathname.startsWith('/file/'))return Response.json(backup);
    const method=url.pathname.split('/').at(-1),data=await request.json();calls.push({method,data});
    const visibleText=data.parse_mode==='HTML'?data.text?.replace(/<[^>]*>/g,'').replace(/&(amp|lt|gt|quot|#39);/g,'x'):data.text;
    if(['sendMessage','editMessageText'].includes(method)&&visibleText.length>4096)return Response.json({ok:false,error_code:400,description:'message is too long'});
    if(method==='getFile')return Response.json({ok:true,result:{file_id:'backup',file_path:'test.json',file_size:1000}});
    if(method==='getMe')return Response.json({ok:true,result:{id:123456,is_bot:true,username:'KkInstaFixBot'}});
    if(method==='getChatMember')return Response.json({ok:true,result:{status:data.user_id===7?'administrator':'member'}});
    if(method==='editMessageText'&&editFailure){const value=editFailure;if(value.once)editFailure=null;return Response.json({ok:false,error_code:value.code,description:value.description??'cannot edit',parameters:{retry_after:5}});}
    if(method==='deleteMessage'&&deleteFail)return Response.json({ok:false,error_code:403,description:'cannot delete'});
    if(method==='sendMessage'&&failure){const value=failure;if(failure.once)failure=null;return Response.json({ok:false,error_code:value.code,description:value.description??'cannot send',parameters:{retry_after:5}});}
    return Response.json({ok:true,result:method==='sendMessage'?{message_id:1000+calls.length,chat:{id:data.chat_id,type:'supergroup'},text:data.text}:true});
  }});
let db;
before(async()=>{
  db=await mf.getD1Database('DB');
  const schema=await readFile(new URL('../schema.sql',import.meta.url),'utf8');
  // D1 exec accepts one complete statement per line; SQL has no semicolons in literals.
  for(const statement of schema.split(';').map(s=>s.trim()).filter(Boolean))await db.prepare(statement).run();
});
after(()=>mf.dispose());
const dispatch=(path,body,headers={})=>mf.dispatchFetch('https://bot.example'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json',...headers},body:body?JSON.stringify(body):undefined});
let id=0;
const message=(text,user=5,chat=-1001,extra={})=>({message_id:++id,chat:{id:chat,type:'supergroup'},from:{id:user,first_name:'Alice <3 & Bob'},text,...extra});
const update=async m=>{
  const body=m.update_id?m:{update_id:++id,message:m};
  const response=await dispatch('/webhook',body,{'X-Telegram-Bot-Api-Secret-Token':'webhook-test-secret'});
  return {response,body};
};

for(const [raw,expected] of [
  ['https://twitter.com/u/status/1?s=20&t=tracking','https://twitter.com/u/status/1'],
  ['https://instagram.com/reel/abc?igsh=xyz','https://instagram.com/reel/abc'],
  ['https://youtu.be/abc?si=tracking&t=30','https://www.youtube.com/watch?v=abc&t=30'],
  ['https://youtube.com/shorts/abc?si=tracking','https://www.youtube.com/watch?v=abc'],
  ['https://amazon.co.uk/title/dp/B00ABC1234?tag=x','https://amazon.co.uk/dp/B00ABC1234'],
  ['https://example.com/a?keep=1&utm_source=x#frag','https://example.com/a?keep=1#frag'],
  ['https://weibo.com/123','https://weibo.com/123'],
  ['https://instagram.com/user/','https://instagram.com/user/'],
  ['https://vxtwitter.com/u/status/1','https://twitter.com/u/status/1'],
])test('link parity: '+raw,async()=>assert.equal((await fixLink(raw)).url,expected));

test('disabled platforms remain completely unchanged',async()=>assert.equal((await fixLink('https://twitter.com/u/status/1?t=x',{}, {}, {twitter:0})).url,'https://twitter.com/u/status/1?t=x'));
test('no-account frontend retains separate preview',async()=>assert.deepEqual(await fixLink('https://twitter.com/u/status/1',{}, {twitter:'xcancel'}),{url:'https://xcancel.com/u/status/1',preview:'https://vxtwitter.com/u/status/1',platform:'twitter',key:'xcancel',previewKey:'vx',raw:'https://twitter.com/u/status/1'}));
test('multiple URLs keep message context, punctuation and fragments',async()=>{
  const r=await processText('See https://twitter.com/u/status/1, and https://example.com/a?utm_source=x#frag.',{}, {}, {});
  assert.equal(r.text,'See https://twitter.com/u/status/1, and https://example.com/a#frag.');
});
test('YouTube timestamps and functional generic parameters survive cleaning',()=>assert.equal(stripTracking('https://youtube.com/watch?v=id&t=30&si=x'),'https://youtube.com/watch?v=id&t=30'));
test('provider matching refuses lookalike domains',()=>assert.equal(platformFor(new URL('https://twitter.com.evil.example/u')),null));
test('share links expand under bounded redirects',async()=>{
  const calls=[];const r=await fixLink('https://vm.tiktok.com/abc',{}, {}, {},async url=>{calls.push(url);return new Response(null,{status:302,headers:{location:'https://www.tiktok.com/@u/video/1'}});});
  assert.equal(r.url,'https://www.tiktok.com/@u/video/1');assert.equal(r.preview,'https://tnktok.com/@u/video/1');assert.equal(calls.length,1);
});
test('HTTP 403 on a provider does not prematurely declare a link failed',async()=>{
  let count=0;const r=await fixLink('https://twitter.com/u/status/1',{}, {}, {},async()=>{count++;return new Response(null,{status:403});});
  assert.equal(r.url,'https://twitter.com/u/status/1');assert.equal(r.preview,'https://vxtwitter.com/u/status/1');assert.equal(count,0);
});
test('too many links are bounded below Worker subrequest limits',async()=>assert.equal((await processText(Array.from({length:9},(_,i)=>`https://x.com/u/status/${i}`).join(' '),{}, {}, {})).tooMany,true));
test('webhook rejects forged requests before activation',async()=>assert.equal((await dispatch('/webhook',{update_id:123})).status,403));
test('private setup requires authorization',async()=>assert.equal((await dispatch('/setup',{token})).status,403));
test('setup page renders without leaking activation keys',async()=>{const r=await dispatch('/setup');assert.equal(r.status,200);assert.match(await r.text(),/Telegram bot token/);assert.equal(r.headers.get('Referrer-Policy'),'no-referrer');});
test('activation verifies bot and registers authenticated webhook without dropping updates',async()=>{
  const r=await dispatch('/setup',{token},{Authorization:'Bearer '+bootstrap});const activation=await r.json();assert.equal(r.status,200,JSON.stringify(activation));assert.equal(activation.username,'KkInstaFixBot');
  const call=calls.find(c=>c.method==='setWebhook');assert.equal(call.data.url,'https://bot.example/webhook');assert.equal(call.data.drop_pending_updates,false);assert.equal(call.data.max_connections,1);
  const stored=await db.prepare('SELECT * FROM runtime_config').first();assert.equal(stored.activated,1);assert.ok(!stored.token_cipher.includes(token));
});
test('activation link is closed after success',async()=>assert.equal((await dispatch('/setup',{token},{Authorization:'Bearer '+bootstrap})).status,409));
test('health exposes readiness without secrets',async()=>{const body=await(await dispatch('/health')).text();assert.match(body,/"active":true/);assert.ok(!body.includes(token));assert.ok(!body.includes(bootstrap));});
test('normal rewrite sends first, escapes HTML and deletes original once',async()=>{
  calls.length=0;const {response}=await update(message('https://twitter.com/u/status/100'));assert.equal(response.status,200);
  const send=calls.find(c=>c.method==='sendMessage');assert.match(send.data.text,/href="https:\/\/twitter.com\//);assert.match(send.data.text,/Alice &lt;3 &amp; Bob/);
  assert.equal(send.data.link_preview_options.url,'https://vxtwitter.com/u/status/100');assert.match(send.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data,/^e:twitter:/);
  assert.deepEqual(calls.map(c=>c.method),['sendMessage','deleteMessage']);
});
test('duplicate webhook delivery never sends twice',async()=>{
  calls.length=0;const body={update_id:++id,message:message('https://twitter.com/u/status/101')};await update(body);await update(body);
  assert.equal(calls.filter(c=>c.method==='sendMessage').length,1);
});
test('opt-out persists per user and chat while others continue',async()=>{
  await update(message('/optout',6,-1002));calls.length=0;
  await update(message('https://twitter.com/u/status/102',6,-1002));assert.equal(calls.length,0);
  await update(message('https://twitter.com/u/status/103',5,-1002));assert.equal(calls.filter(c=>c.method==='sendMessage').length,1);
  assert.ok(await db.prepare('SELECT * FROM optout_users WHERE chat_id=-1002 AND user_id=6').first());
  await update(message('/optin',6,-1002));calls.length=0;await update(message('https://twitter.com/u/status/104',6,-1002));assert.equal(calls.filter(c=>c.method==='sendMessage').length,1);
});
test('send permission failure preserves original and releases dedup for a new attempt',async()=>{
  failure={code:403};calls.length=0;const m=message('https://twitter.com/u/status/105',5,-1003);await update(m);
  assert.deepEqual(calls.map(c=>c.method),['sendMessage']);assert.equal((await db.prepare("SELECT * FROM recent_events WHERE kind='fix' AND chat_id=-1003").all()).results.length,0);
  failure=null;calls.length=0;await update({...m,message_id:++id});assert.deepEqual(calls.map(c=>c.method),['sendMessage','deleteMessage']);
});
test('flood control requests Telegram retry without a burst or premature deletion',async()=>{
  failure={code:429};calls.length=0;const {response,body}=await update(message('https://twitter.com/u/status/106',5,-1004));
  assert.equal(response.status,503);assert.equal(response.headers.get('Retry-After'),'5');assert.equal(calls.length,1);
  assert.equal(await db.prepare('SELECT * FROM deliveries WHERE update_id=?').bind(body.update_id).first(),null);failure=null;
});
test('format rejection falls back to useful rewritten text',async()=>{
  failure={code:400,once:true};calls.length=0;await update(message('https://twitter.com/u/status/107',5,-1005));
  const sends=calls.filter(c=>c.method==='sendMessage');assert.equal(sends.length,2);assert.ok(sends[1].data.entities.some(e=>e.type==='text_link'&&e.url.startsWith('https://twitter.com/')));assert.ok(!sends[1].data.parse_mode);
});
test('delete permission failure does not resend or erase delivery',async()=>{
  deleteFail=true;calls.length=0;await update(message('https://twitter.com/u/status/108',5,-1006));
  assert.deepEqual(calls.map(c=>c.method),['sendMessage','deleteMessage']);deleteFail=false;
});
for(const kind of ['edited_message','channel_post','edited_channel_post'])test(kind+' reaches link rewrite',async()=>{
  calls.length=0;await update({update_id:++id,[kind]:message('https://twitter.com/u/status/'+id,5,-2000-id)});
  assert.equal(calls.filter(c=>c.method==='sendMessage').length,1);assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
});
test('caption preserves media and reply/thread context',async()=>{
  calls.length=0;await update(message(undefined,5,-2008,{caption:'Photo https://twitter.com/u/status/111',message_thread_id:42}));
  const send=calls.find(c=>c.method==='sendMessage');assert.equal(send.data.message_thread_id,42);assert.ok(send.data.reply_parameters.message_id);assert.ok(!calls.some(c=>c.method==='deleteMessage'));
});
test('regular users cannot change providers',async()=>{
  calls.length=0;await update(message('/setprovider twitter fx',5,-2009));assert.match(calls.find(c=>c.method==='sendMessage').data.text,/Only admins/);
  assert.equal(await db.prepare('SELECT * FROM provider_settings WHERE chat_id=-2009').first(),null);
});
test('admin provider choice persists and is applied',async()=>{
  await update(message('/setprovider twitter fx',7,-2010));calls.length=0;await update(message('https://twitter.com/u/status/112',5,-2010));assert.equal(calls.find(c=>c.method==='sendMessage').data.link_preview_options.url,'https://fxtwitter.com/u/status/112');
});
test('per-message provider button edits the bot post',async()=>{
  calls.length=0;await update({update_id:++id,callback_query:{id:'callback1',from:{id:5},data:'e:twitter:1',message:{message_id:1000,chat:{id:-2010,type:'supergroup'},text:'https://vxtwitter.com/u/status/112'}}});
  assert.deepEqual(calls.map(c=>c.method),['answerCallbackQuery','editMessageText']);assert.equal(calls[1].data.link_preview_options.url,'https://fxtwitter.com/u/status/112');assert.match(calls[1].data.text,/twitter.com/);
});
test('inline links are answered without membership or deleting anything',async()=>{
  calls.length=0;await update({update_id:++id,inline_query:{id:'inline1',from:{id:5},query:'https://twitter.com/u/status/113'}});
  assert.equal(calls.length,1);assert.equal(calls[0].method,'answerInlineQuery');assert.match(calls[0].data.results[0].input_message_content.message_text,/twitter.com/);
});
test('transport timeout is not blindly retried by fallback chain',async()=>{
  let count=0;const tg=new Telegram(token,async()=>{count++;throw new Error('timeout');});
  await assert.rejects(()=>tg.deliver(-1,'html','plain'),e=>e instanceof TelegramError&&e.code===0);assert.equal(count,1);
});


test('interrupted pre-send processing remains retryable without concurrent duplicates',async()=>{
  const m=message('https://twitter.com/u/status/120',5,-2020),body={update_id:++id,message:m};
  await db.prepare("INSERT INTO deliveries VALUES(?,'processing',?)").bind(body.update_id,Math.floor(Date.now()/1000)).run();
  calls.length=0;assert.equal((await update(body)).response.status,503);assert.equal(calls.length,0);
  await db.prepare('UPDATE deliveries SET ts=ts-121 WHERE update_id=?').bind(body.update_id).run();
  assert.equal((await update(body)).response.status,200);assert.equal(calls.filter(c=>c.method==='sendMessage').length,1);
});
test('ambiguous in-flight send is not sent twice on webhook redelivery',async()=>{
  const body={update_id:++id,message:message('https://twitter.com/u/status/121',5,-2021)};
  await db.prepare("INSERT INTO deliveries VALUES(?,'sending',?)").bind(body.update_id,Math.floor(Date.now()/1000)-200).run();
  calls.length=0;assert.equal((await update(body)).response.status,200);assert.equal(calls.length,0);
});
test('admin JSON import preserves opt-outs and individual settings',async()=>{
  backup={version:1,chat_id:-2022,settings:{sender_mode:'none'},providers:{twitter:'fx'},
    muted_users:[],optout_users:[8],platform_overrides:{spotify:0},
    user_settings:[{user_id:8,chat_id:-2022,key:'sender_mode',value:'username'}]};
  const m=message('/import',7,-2022,{document:{file_id:'backup',file_size:1000}});calls.length=0;
  assert.equal((await update(m)).response.status,200);
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/Settings restored/);
  assert.ok(await db.prepare('SELECT * FROM optout_users WHERE chat_id=-2022 AND user_id=8').first());
  assert.equal((await db.prepare('SELECT * FROM user_settings WHERE chat_id=-2022 AND user_id=8').first()).value,'username');
});

test('diagnostics require the private admin key even after activation',async()=>{
  assert.equal((await dispatch('/admin/status',{})).status,403);
  const response=await dispatch('/admin/status',{}, {Authorization:'Bearer '+bootstrap});
  assert.equal(response.status,200);const body=await response.text();assert.ok(!body.includes(token));assert.match(body,/expected_webhook/);
});

for(const [platform,key,raw,expected] of [
  ['instagram','zz','https://instagram.com/reel/abc?psln=tracking','https://zzinstagram.com/reel/abc'],
  ['instagram','uu','https://instagram.com/p/abc','https://uuinstagram.com/p/abc'],
  ['twitter','ez','https://x.com/u/status/1','https://xeezz.com/u/status/1'],
  ['twitter','twittpr','https://x.com/u/status/1','https://twittpr.com/u/status/1'],
  ['tiktok','ez','https://tiktok.com/@u/video/1','https://tiktokez.com/@u/video/1'],
  ['tiktok','kk','https://tiktok.com/@u/video/1','https://kktiktok.com/@u/video/1'],
  ['tiktok','fix','https://tiktok.com/@u/video/1','https://fixtiktok.com/@u/video/1'],
  ['facebook','bed','https://facebook.com/reel/123','https://facebed.seria.moe/reel/123'],
  ['threads','fix','https://threads.net/@u/post/abc','https://fixthreads.seria.moe/@u/post/abc'],
  ['bilibili','ez','https://bilibili.com/video/BV1g4KKe3EoP','https://bilibiliez.com/video/BV1g4KKe3EoP'],
  ['pinterest','ez','https://pinterest.com/pin/123','https://pinterestez.com/pin/123'],
])test(`updated provider mapping: ${platform}/${key}`,async()=>{
  const fixed=await fixLink(raw,{}, {[platform]:key});
  assert.equal(fixed.preview,expected);
});
test('removed provider selection safely falls back to working default',async()=>{
  assert.equal((await fixLink('https://instagram.com/reel/abc',{}, {instagram:'ez'})).preview,'https://eeinstagram.com/reel/abc');
  assert.equal((await fixLink('https://tiktok.com/@u/video/1',{}, {tiktok:'vx'})).preview,'https://tnktok.com/@u/video/1');
});
test('LinkedIn is cleaned without rewriting to an unverified host',async()=>{
  assert.equal((await fixLink('https://linkedin.com/posts/test?trackingId=123&keep=x')).url,'https://linkedin.com/posts/test?keep=x');
});

// Review counterexamples: assertions describe the behaviour the bot should have.
test('REVIEW: preserve surrounding text before deleting a single-link message',async()=>{
  calls.length=0;const m=message('Please watch this before Friday: https://instagram.com/reel/Review123',5,-4101);
  await update(m);
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.ok(calls.some(c=>c.method==='deleteMessage'),'reproduction must exercise original deletion');
  assert.ok(sent.data.text.includes('Please watch this before Friday'),'caption text is discarded before deleting original');
});
test('REVIEW: commands addressed to another bot must not change this bot',async()=>{
  calls.length=0;await update(message('/disable@SomeOtherBot',7,-4102));
  const row=await db.prepare('SELECT enabled FROM chat_settings WHERE chat_id=-4102').first();
  assert.ok(row===null||row.enabled===1,'command for another bot disabled KkInstafix');
  assert.equal(calls.length,0);
});
test('REVIEW: muted users must not trigger command replies',async()=>{
  await db.prepare('INSERT INTO blocked_users VALUES(-4103,5)').run();
  calls.length=0;await update(message('/start',5,-4103));
  assert.equal(calls.filter(c=>c.method==='sendMessage').length,0,'muted user can still trigger the full help reply');
});
test('REVIEW: valid long messages must not silently lose their rewrite',async()=>{
  calls.length=0;const m=message('a'.repeat(4030)+' https://x.com/a/status/1 https://x.com/b/status/2',5,-4104);
  m.from.first_name='Alice';
  assert.ok(m.text.length<=4096,'input must fit Telegram message limit');
  const {body}=await update(m);
  const result=await db.prepare('SELECT state FROM deliveries WHERE update_id=?').bind(body.update_id).first();
  assert.notEqual(result.state,'rejected','label and rewritten host expansion push output over the Telegram limit; all fallbacks are too long');
});
test('REVIEW: restore a real pre-refresh backup with retired provider keys',async()=>{
  backup={version:1,chat_id:-4105,settings:{enabled:1},providers:{instagram:'ez',facebook:'ez',pinterest:'vx'},muted_users:[],optout_users:[8],platform_overrides:{}};
  calls.length=0;await update(message('/import',7,-4105,{document:{file_id:'backup',file_size:1500}}));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/Settings restored/,'a pre-refresh backup is rejected completely');
  assert.ok(await db.prepare('SELECT * FROM optout_users WHERE chat_id=-4105 AND user_id=8').first());
});

for(const host of ['www.instagram.com','eeinstagram.com'])test('Instagram share cleanup on '+host,async()=>{
  const raw=`https://${host}/reel/Token123/?dlrf=secret&psln=secret&igsh=secret&img_index=2`;
  const fixed=await fixLink(raw);
  assert.equal(new URL(fixed.url).search,'?img_index=2');
  assert.equal(new URL(fixed.preview).search,'?img_index=2');
  assert.equal(new URL(stripTracking(raw)).search,'?img_index=2');
});
test('sanitized clickable target, preview and provider cycle retain surrounding text',async()=>{
  calls.length=0;const chat=-4201;
  await update(message('Watch this: https://instagram.com/reel/Token999/?dlrf=secret&img_index=2',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.ok(!sent.data.text.includes('dlrf'));assert.ok(!sent.data.link_preview_options.url.includes('dlrf'));
  const text='Alice: Watch this: https://eeinstagram.com/reel/Token999/?dlrf=old&img_index=2';
  const url=text.slice(text.indexOf('https:'));
  await update({update_id:++id,callback_query:{id:'preserve-text',from:{id:5},data:sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data,
    message:{message_id:100,chat:{id:chat,type:'supergroup'},text,entities:[{type:'url',offset:text.indexOf('https:'),length:url.length}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.match(edit.data.text,/Watch this:/);assert.ok(!edit.data.text.includes('dlrf'));
  assert.ok(!edit.data.link_preview_options.url.includes('dlrf'));assert.match(edit.data.text,/img_index=2/);
});
test('long rewrite posts a companion reply and preserves the complete original',async()=>{
  calls.length=0;const m=message('a'.repeat(4030)+' https://x.com/a/status/71 https://x.com/b/status/72',5,-4202);
  await update(m);const send=calls.find(c=>c.method==='sendMessage');
  assert.ok(send);assert.ok(send.data.text.length<=4096);assert.equal(send.data.reply_parameters.message_id,m.message_id);
  assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
});
test('commands accept our configured username without case sensitivity',async()=>{
  calls.length=0;await update(message('/disable@kKINstaFIXboT',7,-4203));
  assert.equal((await db.prepare('SELECT enabled FROM chat_settings WHERE chat_id=-4203').first()).enabled,0);
});
test('backup migration rejects unknown provider names atomically',async()=>{
  backup={version:1,chat_id:-4204,settings:{enabled:0},providers:{instagram:'madeup'},optout_users:[8]};
  calls.length=0;await update(message('/import',7,-4204,{document:{file_id:'backup',file_size:1000}}));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/Invalid provider/);
  assert.equal(await db.prepare('SELECT enabled FROM chat_settings WHERE chat_id=-4204').first(),null);
});

test('bare Instagram link sanitizes the hidden clickable target and clean command',async()=>{
  calls.length=0;await update(message('https://www.instagram.com/reel/Bare123/?dlrf=secret&psln=secret',5,-4210));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/href="https:\/\/instagram.com\/reel\/Bare123\/"/);
  assert.equal(sent.data.link_preview_options.url,'https://eeinstagram.com/reel/Bare123/');
  calls.length=0;await update(message('/clean https://eeinstagram.com/reel/Clean123/?dlrf=secret&img_index=2',5,-4211));
  const cleaned=calls.find(c=>c.method==='sendMessage').data.text;
  assert.ok(!cleaned.includes('dlrf'));assert.match(cleaned,/img_index=2/);
});

test('REVIEW: switch the matching social link when an unchanged URL appears first',async()=>{
  calls.length=0;const chat=-5101;
  await update(message('Read https://example.com/info then https://instagram.com/reel/ReviewMix',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  const text='Alice: Read https://example.com/info then https://eeinstagram.com/reel/ReviewMix';
  const first='https://example.com/info',second='https://eeinstagram.com/reel/ReviewMix';
  await update({update_id:++id,callback_query:{id:'mixed-review',from:{id:5},data:sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data.startsWith('e:')).callback_data,
    message:{message_id:100,chat:{id:chat,type:'supergroup'},text,entities:[
      {type:'url',offset:text.indexOf(first),length:first.length},{type:'url',offset:text.indexOf(second),length:second.length}]}}});
  const edited=calls.find(c=>c.method==='editMessageText');
  assert.ok(edited.data.text.includes(first),'provider switch corrupts the unrelated URL');
  assert.ok(!edited.data.text.includes(second),'the Instagram URL was never switched');
});
test('REVIEW: linked text should trigger rewriting',async()=>{
  calls.length=0;const text='Watch this reel';
  await update(message(text,5,-5102,{entities:[{type:'text_link',offset:0,length:text.length,url:'https://instagram.com/reel/ReviewHidden?dlrf=secret'}]}));
  assert.ok(calls.some(c=>c.method==='sendMessage'),'a valid Instagram text_link is silently ignored');
});
test('REVIEW: preserve the URL attached to linked text when rewriting another URL',async()=>{
  calls.length=0;const text='Read details then https://instagram.com/reel/ReviewEntity';
  await update(message(text,5,-5103,{entities:[{type:'text_link',offset:5,length:7,url:'https://example.com/details'}]}));
  assert.ok(calls.some(c=>c.method==='deleteMessage'),'test must exercise deletion');
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.ok(sent.data.text.includes('https://example.com/details')||sent.data.entities?.some(e=>e.url==='https://example.com/details'),'hidden hyperlink is lost when the original is deleted');
});
test('REVIEW: near-limit link alone should still produce a response',async()=>{
  calls.length=0;const prefix='https://x.com/u/status/Long?keep=';
  const text=prefix+'a'.repeat(4096-prefix.length);
  await update(message(text,5,-5104));
  assert.ok(calls.some(c=>c.method==='sendMessage'),'valid message silently skipped after provider expansion');
});

test('entity offsets preserve emoji, leading whitespace and caption hyperlinks',async()=>{
  const text='  📷 Watch this';
  const entities=[{type:'text_link',offset:text.indexOf('Watch'),length:10,url:'https://instagram.com/reel/CaptionEntity/?dlrf=secret'}];
  assert.equal(messageSource({caption:text,caption_entities:entities}),'  📷 Watch this (https://instagram.com/reel/CaptionEntity/?dlrf=secret)');
  calls.length=0;const m=message(undefined,5,-5201,{caption:text,caption_entities:entities,photo:[{file_id:'photo'}]});
  await update(m);const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/Watch this/);assert.match(sent.data.text,/instagram.com/);assert.ok(!sent.data.text.includes('dlrf'));
  assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
  assert.equal(sent.data.reply_parameters.message_id,m.message_id);
});
test('new button targets the correct post even with another provider link first',async()=>{
  calls.length=0;const chat=-5202;
  await update(message('Target https://instagram.com/reel/TargetPost.',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  const text='Earlier https://eeinstagram.com/reel/OtherPost then https://eeinstagram.com/reel/TargetPost.';
  await update({update_id:++id,callback_query:{id:'same-platform',from:{id:5},data:sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data,
    message:{message_id:100,chat:{id:chat,type:'supergroup'},text}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.match(edit.data.text,/eeinstagram.com\/reel\/OtherPost/);
  assert.ok(!edit.data.text.includes('eeinstagram.com/reel/TargetPost'));
  assert.equal(edit.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data.split(':')[3],sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data.split(':')[3]);
});
test('legacy ambiguous button leaves every link untouched',async()=>{
  calls.length=0;await update({update_id:++id,callback_query:{id:'ambiguous',from:{id:5},data:'e:instagram:1',
    message:{message_id:100,chat:{id:-5203,type:'supergroup'},text:'https://eeinstagram.com/reel/One https://eeinstagram.com/reel/Two'}}});
  assert.equal(calls.filter(c=>c.method==='editMessageText').length,0);
  assert.match(calls.find(c=>c.method==='answerCallbackQuery').data.text,/send the link again/);
});
test('switching a hidden post preserves other hidden hyperlinks',async()=>{
  const text='📷 Details and Alice';
  const entities=[{type:'text_link',offset:text.indexOf('Details'),length:7,url:'https://example.com/details'},
    {type:'text_link',offset:text.indexOf('Alice'),length:5,url:'https://eeinstagram.com/reel/HiddenSwitch'}];
  calls.length=0;await update({update_id:++id,callback_query:{id:'hidden-other',from:{id:5},data:'e:instagram:0',
    message:{message_id:100,chat:{id:-5204,type:'supergroup'},text,entities}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.match(edit.data.text,/<a href="https:\/\/example.com\/details">Details<\/a>/);
  assert.match(edit.data.text,/<a href="https:\/\/instagram.com\/reel\/HiddenSwitch">Alice<\/a>/);
});
test('long URL uses a compact clickable label and retains the original',async()=>{
  calls.length=0;const prefix='http://x.com/u/status/VeryLong?keep=';
  const original=prefix+'z'.repeat(4096-prefix.length);const m=message(original,5,-5205);
  const {body}=await update(m);const sends=calls.filter(c=>c.method==='sendMessage');
  assert.equal(sends.length,1);assert.match(sends[0].data.text,/>Open fixed link 1<\/a>/);
  assert.ok(sends[0].data.text.includes('https://x.com/'));assert.equal(new URL(sends[0].data.link_preview_options.url).host,'vxtwitter.com');
  assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
  assert.equal((await db.prepare('SELECT state FROM deliveries WHERE update_id=?').bind(body.update_id).first()).state,'done');
});
test('HTML fallback retains the destination of an unchanged hidden hyperlink',async()=>{
  calls.length=0;failure={code:400,once:true};
  const text='See details https://instagram.com/reel/FallbackEntity';
  await update(message(text,5,-5206,{entities:[{type:'text_link',offset:4,length:7,url:'https://example.com/details'}]}));
  const sends=calls.filter(c=>c.method==='sendMessage');
  assert.equal(sends.length,2);assert.ok(sends[1].data.entities.some(e=>e.url==='https://example.com/details'));
  assert.ok(sends[1].data.entities.some(e=>e.url?.includes('instagram.com')));
});

test('rewritten linked text retains its clickable label',async()=>{
  calls.length=0;const text='📷 Watch the reel';
  await update(message(text,5,-5210,{entities:[{type:'text_link',offset:3,length:14,url:'https://instagram.com/reel/KeepLabel/?dlrf=secret'}]}));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/<a href="https:\/\/instagram.com\/reel\/KeepLabel\/">Watch the reel<\/a>/);
});
test('Telegram rejection of an oversized URL produces an explanation and preserves original',async()=>{
  calls.length=0;failure={code:400,once:true};
  const prefix='http://x.com/u/status/RejectedLong?keep=';
  const m=message(prefix+'z'.repeat(4096-prefix.length),5,-5211);
  await update(m);const sends=calls.filter(c=>c.method==='sendMessage');
  assert.equal(sends.length,2);assert.match(sends[1].data.text,/original message was kept/);
  assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
});

test('linked labels adjacent to other text still rewrite their actual destination',async()=>{
  calls.length=0;const text='Watchthis';
  await update(message(text,5,-5212,{entities:[{type:'text_link',offset:0,length:5,url:'https://instagram.com/reel/Adjacent/?dlrf=secret'}]}));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/<a href="https:\/\/instagram.com\/reel\/Adjacent\/">Watch<\/a>this/);
});


test('clean Instagram URL still receives a proxy preview when visible text is unchanged',async()=>{
  calls.length=0;const raw='https://instagram.com/reel/OfficialClean/';
  const processed=await processText(raw,{}, {}, {});
  assert.equal(processed.text,raw);assert.equal(processed.links.length,1);
  await update(message(raw,5,-5301));const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/href="https:\/\/instagram.com\/reel\/OfficialClean\/"/);
  assert.equal(sent.data.link_preview_options.url,'https://eeinstagram.com/reel/OfficialClean/');
});
test('Instagram provider switching changes only the preview for official clickable links',async()=>{
  calls.length=0;const raw='https://instagram.com/reel/OfficialSwitch/?img_index=2';
  await update(message(raw,5,-5302));const sent=calls.find(c=>c.method==='sendMessage');
  const text='📷 Alice';const entity={type:'text_link',offset:3,length:5,url:raw};
  const data=sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data;
  await update({update_id:++id,callback_query:{id:'official-switch',from:{id:5},data,
    message:{message_id:100,chat:{id:-5302,type:'supergroup'},text,entities:[entity]}}});
  const edited=calls.find(c=>c.method==='editMessageText');
  assert.equal(edited.data.text,'📷 <a href="https://instagram.com/reel/OfficialSwitch/?img_index=2">Alice</a>');
  assert.notEqual(edited.data.link_preview_options.url,sent.data.link_preview_options.url);
  assert.equal(new URL(edited.data.link_preview_options.url).pathname,'/reel/OfficialSwitch/');
  assert.equal(new URL(edited.data.link_preview_options.url).search,'?img_index=2');
});
test('Instagram proxy input becomes official and keeps the selected preview provider',async()=>{
  const fixed=await fixLink('http://eeinstagram.com:8080/reel/ProxyInput/?dlrf=secret&psln=secret&img_index=2',{}, {instagram:'zz'});
  assert.equal(fixed.url,'https://instagram.com/reel/ProxyInput/?img_index=2');
  assert.equal(fixed.preview,'https://zzinstagram.com/reel/ProxyInput/?img_index=2');
});
test('inline Instagram articles click through to official Instagram with proxy previews',async()=>{
  calls.length=0;await update({update_id:++id,inline_query:{id:'official-inline',from:{id:5},query:'https://instagram.com/reel/InlineOfficial/?dlrf=secret'}});
  const content=calls.find(c=>c.method==='answerInlineQuery').data.results[0].input_message_content;
  assert.equal(content.message_text,'https://instagram.com/reel/InlineOfficial/');
  assert.equal(content.link_preview_options.url,'https://eeinstagram.com/reel/InlineOfficial/');
});
test('plain fallback uses official Instagram and preserves the proxy preview',async()=>{
  calls.length=0;failure={code:400,once:true};
  await update(message('https://instagram.com/reel/FallbackOfficial/?dlrf=secret',5,-5303));
  const sends=calls.filter(c=>c.method==='sendMessage');
  assert.equal(sends.length,2);assert.ok(sends[1].data.entities.some(e=>e.url==='https://instagram.com/reel/FallbackOfficial/'));
  assert.ok(!sends[1].data.text.includes('eeinstagram.com'));assert.ok(!sends[1].data.text.includes('dlrf'));
  assert.equal(sends[1].data.link_preview_options.url,'https://eeinstagram.com/reel/FallbackOfficial/');
});

for(const host of ['www.instagram.com','eeinstagram.com'])for(const key of ['xtok','vrfl','NEW_SHARE_TOKEN'])
  test(`Instagram drops dynamic share token ${key} on ${host}`,async()=>{
    const raw=`https://${host}/reel/ChangingTokens/?${key}=secret&img_index=2`;
    const fixed=await fixLink(raw);
    assert.equal(fixed.url,'https://instagram.com/reel/ChangingTokens/?img_index=2');
    assert.equal(fixed.preview,'https://eeinstagram.com/reel/ChangingTokens/?img_index=2');
    assert.equal(new URL(stripTracking(raw)).search,'?img_index=2');
  });
test('dynamic share tokens are absent from message target, preview, inline result and switched provider',async()=>{
  const raw='https://www.instagram.com/reel/LatestTokens/?xtok=secret&vrfl=secret&next_token=secret&img_index=3';
  calls.length=0;await update(message(raw,5,-5401));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/href="https:\/\/instagram.com\/reel\/LatestTokens\/\?img_index=3"/);
  assert.equal(sent.data.link_preview_options.url,'https://eeinstagram.com/reel/LatestTokens/?img_index=3');
  const text='📷 Alice',url='https://instagram.com/reel/LatestTokens/?img_index=3';
  await update({update_id:++id,callback_query:{id:'latest-tokens',from:{id:5},data:sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data,
    message:{message_id:100,chat:{id:-5401,type:'supergroup'},text,entities:[{type:'text_link',offset:3,length:5,url}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.match(edit.data.text,/instagram.com\/reel\/LatestTokens\/\?img_index=3/);
  assert.equal(new URL(edit.data.link_preview_options.url).search,'?img_index=3');
  calls.length=0;await update({update_id:++id,inline_query:{id:'latest-tokens-inline',from:{id:5},query:raw}});
  const content=calls.find(c=>c.method==='answerInlineQuery').data.results[0].input_message_content;
  assert.equal(content.message_text,url);assert.equal(new URL(content.link_preview_options.url).search,'?img_index=3');
});
test('clean command removes new Instagram share tokens while keeping image selection',async()=>{
  calls.length=0;await update(message('/clean https://instagram.com/p/CleanLatest/?vrfl=secret&xtok=secret&unseen=secret&img_index=4',5,-5402));
  assert.equal(calls.find(c=>c.method==='sendMessage').data.text,'https://instagram.com/p/CleanLatest/?img_index=4');
});
test('profile links remove known share tokens without using a post preview provider',async()=>{
  const fixed=await fixLink('https://instagram.com/example/?xtok=secret&vrfl=secret');
  assert.equal(fixed.url,'https://instagram.com/example/');assert.equal(fixed.preview,fixed.url);
});
test('unknown parameters on other sites remain functional',async()=>{
  const raw='https://example.com/reel/a?xtok=needed&vrfl=needed&unseen=needed';
  assert.equal((await fixLink(raw)).url,raw);
  assert.equal((await fixLink('https://youtube.com/watch?v=abc&t=30')).url,'https://youtube.com/watch?v=abc&t=30');
});

test('hidden Instagram links remove dynamic share tokens in HTML and plain fallback',async()=>{
  calls.length=0;failure={code:400,once:true};
  const raw='https://instagram.com/reel/HiddenDynamic/?xtok=secret&vrfl=secret&future_key=secret';
  const text='Watch this';
  await update(message(text,5,-5403,{entities:[{type:'text_link',offset:0,length:text.length,url:raw}]}));
  const sends=calls.filter(c=>c.method==='sendMessage');
  assert.equal(sends.length,2);
  for(const send of sends) {
    assert.ok(!/xtok|vrfl|future_key|secret/.test(send.data.text));
    assert.equal(new URL(send.data.link_preview_options.url).search,'');
  }
  assert.match(sends[0].data.text,/<a href="https:\/\/instagram.com\/reel\/HiddenDynamic\/">Watch this<\/a>/);
});
test('buttons created before dynamic token cleanup still switch and sanitize their link',async()=>{
  calls.length=0;const path='/reel/LegacyTokens/?vrfl=secret';
  await update({update_id:++id,callback_query:{id:'old-token-button',from:{id:5},data:'e:instagram:0:'+hash(path).slice(0,12),
    message:{message_id:100,chat:{id:-5404,type:'supergroup'},text:'Alice',entities:[{type:'text_link',offset:0,length:5,url:'https://instagram.com'+path}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.ok(edit);assert.equal(edit.data.text,'<a href="https://instagram.com/reel/LegacyTokens/">Alice</a>');
  assert.equal(new URL(edit.data.link_preview_options.url).search,'');
});


test('Instagram preview appears above linked attribution with only a retry button',async()=>{
  calls.length=0;const m=message('https://instagram.com/reel/VisualLayout/?xtok=secret',5,-5501);
  m.from.first_name='elSapo';await update(m);
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.equal(sent.data.text,'<i>Shared by <a href="https://instagram.com/reel/VisualLayout/">elSapo</a></i>');
  assert.equal(sent.data.link_preview_options.show_above_text,true);
  assert.equal(sent.data.link_preview_options.prefer_large_media,true);
  assert.equal(sent.data.reply_markup.inline_keyboard.length,1);
  assert.equal(sent.data.reply_markup.inline_keyboard[0].length,1);
  const [retry]=sent.data.reply_markup.inline_keyboard[0];
  assert.ok(!retry.url);
  assert.equal(retry.text,'↻ Retry preview');assert.match(retry.callback_data,/^e:instagram:/);
});
test('Instagram layout preserves surrounding text before sender attribution',async()=>{
  calls.length=0;await update(message('Please watch https://instagram.com/reel/ContextLayout/ before Friday.',5,-5502));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.ok(sent.data.text.startsWith('Please watch https://instagram.com/reel/ContextLayout/ before Friday.'));
  assert.match(sent.data.text,/\n\n<i>Shared by /);
  assert.equal(sent.data.link_preview_options.show_above_text,true);
});
test('retry keeps preview above text and removes the duplicate Instagram button',async()=>{
  calls.length=0;const url='https://instagram.com/reel/RetryLayout/';
  await update({update_id:++id,callback_query:{id:'layout-retry',from:{id:5},data:'e:instagram:0',
    message:{message_id:100,chat:{id:-5503,type:'supergroup'},text:'Shared by elSapo',
      entities:[{type:'text_link',offset:10,length:6,url}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.equal(edit.data.link_preview_options.show_above_text,true);
  assert.equal(edit.data.reply_markup.inline_keyboard[0].length,1);
  assert.equal(edit.data.reply_markup.inline_keyboard[0][0].text,'↻ Retry preview');
  assert.ok(!edit.data.reply_markup.inline_keyboard[0][0].url);
  assert.match(edit.data.text,/Shared by <a href="https:\/\/instagram.com\/reel\/RetryLayout\/">elSapo<\/a>/);
});
test('sender mode none has no attribution and keeps official Instagram controls',async()=>{
  await db.prepare("INSERT INTO chat_settings(chat_id,sender_mode) VALUES(-5504,'none')").run();
  calls.length=0;await update(message('https://instagram.com/reel/AnonymousLayout/',5,-5504));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.ok(!sent.data.text.includes('Shared by'));assert.ok(!sent.data.text.includes('Alice'));
  assert.match(sent.data.text,/href="https:\/\/instagram.com\/reel\/AnonymousLayout\/"/);
  assert.equal(sent.data.reply_markup.inline_keyboard[0].length,1);
  assert.ok(!sent.data.reply_markup.inline_keyboard[0][0].url);
});

for(const key of ['kkclip','kk'])test('retired Instagram option falls back and backup restores: '+key,async()=>{
  const chat=key==='kk'?-5601:-5602;
  await db.prepare('INSERT INTO provider_settings VALUES(?,?,?)').bind(chat,'instagram',key).run();
  calls.length=0;await update(message('https://instagram.com/reel/RetiredProvider/',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.equal(sent.data.link_preview_options.url,'https://eeinstagram.com/reel/RetiredProvider/');
  backup={version:1,chat_id:chat,providers:{instagram:key}};
  calls.length=0;await update(message('/import',7,chat,{document:{file_id:'backup',file_size:1000}}));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/Settings restored/);
  assert.equal((await db.prepare('SELECT provider FROM provider_settings WHERE chat_id=? AND platform=?').bind(chat,'instagram').first()).provider,'ee');
});
for(const host of ['kkclip.com','kkinstagram.com'])test('retired Instagram host converts to official link and default preview: '+host,async()=>{
  const fixed=await fixLink(`https://${host}/reel/RetiredHost/?xtok=secret`);
  assert.equal(fixed.url,'https://instagram.com/reel/RetiredHost/');
  assert.equal(fixed.preview,'https://eeinstagram.com/reel/RetiredHost/');
});
test('Instagram retry rotation contains no retired providers',async()=>{
  calls.length=0;await update(message('/providers',5,-5603));
  const text=calls.find(c=>c.method==='sendMessage').data.text;
  const instagram=text.split('<b>instagram</b>:')[1].split('\n')[1];
  assert.ok(!instagram.includes('kk'));assert.match(instagram,/vx, ee, uu, zz/);
});


test('native YouTube stays default and uses the shared layout for a clean watch URL',async()=>{
  const raw='https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc&t=30';
  assert.equal((await fixLink(raw)).url,raw);assert.equal((await fixLink(raw)).preview,raw);
  calls.length=0;await update(message(raw,5,-5701));
  const sent=calls.find(c=>c.method==='sendMessage');assert.match(sent.data.text,/^<i>Shared by /);assert.equal(sent.data.link_preview_options.url,raw);
});
test('optional Koutube preview preserves official YouTube link, video, playlist and timestamps',async()=>{
  const fixed=await fixLink('https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc&index=2&t=30&si=secret&feature=shared',{}, {youtube:'koutube'});
  assert.equal(fixed.url,'https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLabc&index=2&t=30');
  assert.equal(fixed.preview,'https://koutube.com/watch?v=dQw4w9WgXcQ&list=PLabc&index=2&t=30');
});
for(const raw of ['https://youtu.be/dQw4w9WgXcQ?t=30&si=secret','https://youtube.com/shorts/dQw4w9WgXcQ?t=30'])
 test('Koutube handles canonical short link: '+raw,async()=>{
  const fixed=await fixLink(raw,{}, {youtube:'koutube'});
  assert.equal(fixed.preview,'https://koutube.com/watch?v=dQw4w9WgXcQ&t=30');
  assert.equal(fixed.url,'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30');
 });
test('YouTube provider selection produces a Koutube preview without external probes',async()=>{
  const chat=-5702;await update(message('/setprovider youtube koutube',7,chat));
  calls.length=0;await update(message('https://www.youtube.com/watch?v=dQw4w9WgXcQ',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.equal(sent.data.link_preview_options.url,'https://koutube.com/watch?v=dQw4w9WgXcQ');
  assert.match(sent.data.text,/href="https:\/\/www.youtube.com\/watch\?v=dQw4w9WgXcQ"/);
});
test('YouTube retry switches preview while keeping official destination',async()=>{
  calls.length=0;await update({update_id:++id,callback_query:{id:'youtube-retry',from:{id:5},data:'e:youtube:1',
    message:{message_id:100,chat:{id:-5703,type:'supergroup'},text:'Alice',entities:[{type:'text_link',offset:0,length:5,url:'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30'}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.equal(edit.data.link_preview_options.url,'https://koutube.com/watch?v=dQw4w9WgXcQ&t=30');
  assert.match(edit.data.text,/href="https:\/\/www.youtube.com\/watch\?v=dQw4w9WgXcQ&amp;t=30"/);
});
for(const [key,host] of [['boobsky','boobsky.app'],['vx','vxbsky.app']])test('verified Bluesky option: '+key,async()=>{
  const fixed=await fixLink('https://bsky.app/profile/bsky.app/post/3n22yg6lg2k2f',{}, {bluesky:key});
  assert.equal(fixed.preview,`https://${host}/profile/bsky.app/post/3n22yg6lg2k2f`);
});
test('YouTube opt-out and platform disabling remain effective with Koutube selected',async()=>{
  const raw='https://youtu.be/dQw4w9WgXcQ?si=secret';
  assert.equal((await fixLink(raw,{}, {youtube:'koutube'},{youtube:0})).url,raw);
  await update(message('/setprovider youtube koutube',7,-5704));await update(message('/optout',5,-5704));
  calls.length=0;await update(message(raw,5,-5704));assert.equal(calls.length,0);
});


for(const [key,host] of [['to','toinstagram.com'],['embeds','ig.embeds.now'],['revived','fkinstagram.com'],['ins','ins.so']])
 test('Kyrela Instagram provider preserves official URL and cleaned preview: '+key,async()=>{
  const raw='https://instagram.com/reel/C6bfaFzIqqR/?unknown_share=secret&img_index=2';
  const fixed=await fixLink(raw,{}, {instagram:key});
  assert.equal(fixed.url,'https://instagram.com/reel/C6bfaFzIqqR/?img_index=2');
  assert.equal(fixed.preview,`https://${host}/reel/C6bfaFzIqqR/?img_index=2`);
  const reused=await fixLink(`https://${host}/reel/C6bfaFzIqqR/?unknown_share=secret`);
  assert.equal(reused.url,'https://instagram.com/reel/C6bfaFzIqqR/');
  assert.equal(reused.preview,'https://eeinstagram.com/reel/C6bfaFzIqqR/');
 });
for(const path of ['/grimkujow/p/DKMv_h9o_Oj/','/olafurw/reel/C6bfaFzIqqR/','/reels/C6bfaFzIqqR/'])
 test('Instagram post path from comparison table is recognized and sanitized: '+path,async()=>{
  const fixed=await fixLink('https://instagram.com'+path+'?new_token=secret&img_index=2',{}, {instagram:'revived'});
  assert.equal(fixed.preview,'https://fkinstagram.com'+path+'?img_index=2');
  assert.equal(fixed.url,'https://instagram.com'+path+'?img_index=2');
  assert.equal(new URL(stripTracking('https://instagram.com'+path+'?new_token=secret&img_index=2')).search,'?img_index=2');
 });
test('old Instagram7 URLs move to official Instagram and the active preview default',async()=>{
  const fixed=await fixLink('https://instagram7.com/reel/C6bfaFzIqqR/?xtok=secret');
  assert.equal(fixed.url,'https://instagram.com/reel/C6bfaFzIqqR/');
  assert.equal(fixed.preview,'https://eeinstagram.com/reel/C6bfaFzIqqR/');
});
test('Kyrela provider can be selected and retried with official linked attribution',async()=>{
  const chat=-5801;await update(message('/setprovider instagram revived',7,chat));
  calls.length=0;await update(message('https://instagram.com/reel/RevivedRuntime/?xtok=secret',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.equal(sent.data.link_preview_options.url,'https://fkinstagram.com/reel/RevivedRuntime/');
  assert.match(sent.data.text,/href="https:\/\/instagram.com\/reel\/RevivedRuntime\/"/);
  const data=sent.data.reply_markup.inline_keyboard.flat().find(b=>b.callback_data).callback_data;
  await update({update_id:++id,callback_query:{id:'kyrela-retry',from:{id:5},data,
    message:{message_id:100,chat:{id:chat,type:'supergroup'},text:'Alice',entities:[{type:'text_link',offset:0,length:5,url:'https://instagram.com/reel/RevivedRuntime/'}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');
  assert.ok(!/kkclip|kkinstagram/.test(edit.data.link_preview_options.url));
  assert.equal(edit.data.reply_markup.inline_keyboard[0].length,1);
  assert.match(edit.data.text,/href="https:\/\/instagram.com\/reel\/RevivedRuntime\/"/);
});


// Audit every configured provider, including optional frontends, against the
// same renderer and cleanup rules. External service health is tested separately.
for(const [platform,config] of Object.entries(PROVIDERS))for(const key of Object.keys(config.options))
 test(`shared layout and sanitization audit: ${platform}/${key}`,async()=>{
  const path=platform==='instagram'?'/reel/CatalogueAudit/':platform==='youtube'?'/watch?v=CatalogueAudit':'/content/CatalogueAudit';
  const separator=path.includes('?')?'&':'?';
  const raw=`https://${config.domains[0]}${path}${separator}si=secret&gclid=secret&utm_future=secret&keep=needed`;
  const result=await processText(raw,{}, {[platform]:key},{weibo:1},async()=>new Response(null,{status:200}));
  assert.equal(result.links.length,1);
  const link=result.links[0];
  for(const target of [link.url,link.preview]) {
    assert.ok(!target.includes('secret'));assert.ok(!/gclid|utm_future|[?&]si=/.test(target));
  }
  if(!Object.hasOwn(config.noauth_embed??{},key))assert.equal(new URL(link.url).hostname,config.domains[0]);
  else assert.equal(new URL(link.url).hostname,config.options[key]);
  if(platform!=='instagram')assert.equal(new URL(link.url).searchParams.get('keep'),'needed');
  const formatted=formatRepost({text:raw,plainText:result.text,links:result.links,label:'Alice <3 & Bob'});
  assert.match(formatted.html,/^<i>Shared by <a href=/);
  assert.ok(!formatted.html.includes('secret'));assert.ok(!formatted.plain.includes('secret'));
 });
test('YouTube share analytics removed without losing video, playlist or playback position',async()=>{
  const raw='https://youtube.com/watch?v=abc&list=PL123&index=2&t=1m30s&start=90&end=120&si=secret&feature=shared&pp=secret&ab_channel=secret&source_ve_path=secret&gclid=secret&utm_new=secret';
  const fixed=await fixLink(raw,{}, {youtube:'koutube'});
  for(const target of [fixed.url,fixed.preview]) {
    const q=new URL(target).searchParams;
    assert.deepEqual([...q.keys()],['v','list','index','t','start','end']);
    assert.equal(q.get('t'),'1m30s');assert.equal(q.get('list'),'PL123');
  }
});
for(const host of ['koutube.com','koutu.be'])test('pasted YouTube proxy returns cleaned official URL: '+host,async()=>{
  const path=host==='koutu.be'?'/abc':'/watch?v=abc';
  const fixed=await fixLink(`https://${host}${path}${path.includes('?')?'&':'?'}si=secret&utm_new=secret&t=30`);
  assert.equal(fixed.url,'https://www.youtube.com/watch?v=abc&t=30');
  assert.equal(fixed.preview,fixed.url);
});
test('platform-specific host rules also clean provider URLs',async()=>{
  assert.equal(stripTracking('https://pinterestez.com/pin/1?rs=secret&amp=secret&keep=needed'),'https://pinterestez.com/pin/1?keep=needed');
  assert.equal(stripTracking('https://koutube.com/watch?v=abc&pp=secret&feature=secret&gclid=secret&t=30'),'https://koutube.com/watch?v=abc&t=30');
  assert.equal(stripTracking('https://xhslink.xky.us/note/1?xsec_token=needed&xsec_source=pc_share&utm_new=secret'),'https://xhslink.xky.us/note/1?xsec_token=needed&xsec_source=pc_share');
});
for(const [i,raw,expectedHost] of [
  [0,'https://youtube.com/shorts/RuntimeYoutube?si=secret&utm_new=secret','www.youtube.com'],
  [1,'https://x.com/a/status/RuntimeTwitter?gclid=secret&utm_new=secret','x.com'],
  [2,'https://tiktok.com/@a/video/RuntimeTiktok?gclid=secret&utm_new=secret','tiktok.com'],
  [3,'https://reddit.com/r/a/comments/RuntimeReddit?rdt=secret&utm_new=secret','reddit.com'],
  [4,'https://facebook.com/reel/RuntimeFacebook?mibextid=secret&comment_id=10&reply_comment_id=20','facebook.com'],
  [5,'https://bsky.app/profile/a/post/RuntimeBluesky?utm_new=secret','bsky.app'],
]) {
  test('runtime shared presentation and official sanitized target: '+expectedHost,async()=>{
    calls.length=0;await update(message(raw,5,-5900-i));
    const sent=calls.find(c=>c.method==='sendMessage');assert.ok(sent);
    assert.match(sent.data.text,/^<i>Shared by <a href=/);
    assert.ok(!sent.data.text.includes('secret'));assert.ok(!sent.data.link_preview_options.url.includes('secret'));
    assert.equal(sent.data.link_preview_options.show_above_text,true);
    const target=sent.data.text.match(/href="([^"]+)/)[1].replaceAll('&amp;','&');
    assert.equal(new URL(target).hostname,expectedHost);
    if(expectedHost==='facebook.com')assert.equal(new URL(target).searchParams.get('comment_id'),'10');
    if(sent.data.reply_markup)assert.equal(sent.data.reply_markup.inline_keyboard[0].length,1);
  });
}
test('retry upgrades a recorded legacy YouTube emoji header to shared attribution',async()=>{
  const chat=-5920,idMessage=777;
  await db.prepare('INSERT INTO rewritten_messages VALUES(?,?,?,?,?)').bind(chat,idMessage,'https://youtube.com/watch?v=abc','Alice',Math.floor(Date.now()/1000)).run();
  calls.length=0;await update({update_id:++id,callback_query:{id:'legacy-layout-upgrade',from:{id:5},data:'e:youtube:1',
    message:{message_id:idMessage,chat:{id:chat,type:'supergroup'},text:'▶️ Alice',entities:[{type:'text_link',offset:3,length:5,url:'https://youtube.com/watch?v=abc&si=secret'}]}}});
  const edit=calls.find(c=>c.method==='editMessageText');assert.ok(edit);
  assert.equal(edit.data.text,'<i>Shared by <a href="https://youtube.com/watch?v=abc">Alice</a></i>');
  assert.equal(edit.data.link_preview_options.show_above_text,true);
});
test('caption and multi-platform messages use the same bottom attribution',async()=>{
  calls.length=0;await update(message(undefined,5,-5921,{caption:'Compare https://x.com/a/status/1 and https://instagram.com/reel/Compare/',photo:[{file_id:'photo'}]}));
  const sent=calls.find(c=>c.method==='sendMessage');assert.ok(sent.data.text.startsWith('Compare '));
  assert.match(sent.data.text,/\n\n<i>Shared by /);assert.equal(sent.data.link_preview_options.show_above_text,true);
  assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
});

test('YouTube canonicalization keeps playlist and playback settings on short links',async()=>{
  const fixed=await fixLink('https://youtu.be/abc?list=PL123&index=2&t=30&start=20&end=90&si=secret&utm_new=secret',{}, {youtube:'koutube'});
  for(const target of [fixed.url,fixed.preview]) {
    const q=new URL(target).searchParams;
    assert.equal(q.get('list'),'PL123');assert.equal(q.get('index'),'2');
    assert.equal(q.get('t'),'30');assert.equal(q.get('start'),'20');assert.equal(q.get('end'),'90');
    assert.ok(!target.includes('secret'));
  }
});

// Full-message formatting, inline delivery, recovery and read-only diagnostics.
test('nested formatting and UTF-16 ranges survive URL shortening and emoji',async()=>{
  const raw='https://instagram.com/reel/Nested/?xtok=secret';
  const text='📷 Watch '+raw+' now';
  const entities=[{type:'bold',offset:3,length:text.length-3},{type:'italic',offset:3,length:5},
    {type:'underline',offset:9,length:raw.length},{type:'url',offset:9,length:raw.length}];
  const result=await processText(messageSource({text,entities}),{}, {}, {});
  const formatted=formatRepost({text,entities,plainText:result.text,links:result.links,label:'Alice'});
  assert.match(formatted.html,/<b><i>Watch<\/i> /);assert.match(formatted.html,/<u>https:\/\/instagram.com\/reel\/Nested\/<\/u>/);
  assert.ok(!formatted.html.includes('secret'));
  const bold=formatted.fallback.entities.find(e=>e.type==='bold');
  assert.equal(formatted.fallback.text.slice(bold.offset,bold.offset+bold.length),'Watch https://instagram.com/reel/Nested/ now');
});
for(const [type,expected] of [['bold','<b>label</b>'],['italic','<i>label</i>'],['underline','<u>label</u>'],
  ['strikethrough','<s>label</s>'],['spoiler','<tg-spoiler>label</tg-spoiler>'],['code','<code>label</code>'],
  ['pre','<pre>label</pre>'],['blockquote','<blockquote>label</blockquote>'],['expandable_blockquote','<blockquote expandable>label</blockquote>']])
 test('preserves Telegram formatting: '+type,()=>assert.equal(entityHTML('label',[{type,offset:0,length:5}]),expected));
test('language code, text mentions and custom emoji are escaped and preserved',()=>{
  assert.equal(entityHTML('x < y',[{type:'pre',offset:0,length:5,language:'python'}]),'<pre><code class="language-python">x &lt; y</code></pre>');
  assert.equal(entityHTML('Alice',[{type:'text_mention',offset:0,length:5,user:{id:5}}]),'<a href="tg://user?id=5">Alice</a>');
  assert.equal(entityHTML('😀',[{type:'custom_emoji',offset:0,length:2,custom_emoji_id:'123'}]),'<tg-emoji emoji-id="123">😀</tg-emoji>');
});
test('code entities do not acquire forbidden nested URL entities',async()=>{
  const text='https://instagram.com/reel/Code/?xtok=secret',entities=[{type:'code',offset:0,length:text.length}];
  const result=await processText(messageSource({text,entities}),{}, {}, {});
  const formatted=formatRepost({text,entities,plainText:result.text,links:result.links,label:''});
  assert.equal(formatted.html,'<code>https://instagram.com/reel/Code/</code>');
  assert.deepEqual(formatted.fallback.entities.map(e=>e.type),['code']);
});
test('spoiler link disables preview, attribution hyperlink and retry control',async()=>{
  calls.length=0;const text='https://instagram.com/reel/SecretSpoiler/?xtok=secret';
  await update(message(text,5,-6101,{entities:[{type:'spoiler',offset:0,length:text.length}]}));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/<tg-spoiler>https:\/\/instagram.com\/reel\/SecretSpoiler\/<\/tg-spoiler>/);
  assert.equal(sent.data.link_preview_options.is_disabled,true);assert.ok(!sent.data.reply_markup);
  assert.ok(!sent.data.text.includes('<a href='));
});
test('format fallback preserves spoilers through native entities rather than exposing text',async()=>{
  calls.length=0;failure={code:400,once:true};
  const text='Hidden https://instagram.com/reel/FallbackSpoiler/?xtok=secret';
  await update(message(text,5,-6102,{entities:[{type:'spoiler',offset:0,length:text.length}]}));
  const sends=calls.filter(c=>c.method==='sendMessage');assert.equal(sends.length,2);
  assert.ok(sends[1].data.entities.some(e=>e.type==='spoiler'));
  assert.ok(!sends[1].data.text.includes('secret'));assert.equal(sends[1].data.link_preview_options.is_disabled,true);
  assert.ok(!('fallback_message' in sends[1].data));
});
test('inline mode preserves surrounding text and every supported URL',async()=>{
  calls.length=0;await update({update_id:++id,inline_query:{id:'inline-context-all',from:{id:5},query:'Compare https://x.com/a/status/99?si=secret with https://instagram.com/reel/InlineMulti/?xtok=secret please.'}});
  const content=calls.find(c=>c.method==='answerInlineQuery').data.results[0].input_message_content;
  assert.equal(content.message_text,'Compare https://x.com/a/status/99 with https://instagram.com/reel/InlineMulti/ please.');
  assert.equal(content.link_preview_options.show_above_text,true);
});
test('too many inline links return an explicit limit rather than just the first link',async()=>{
  calls.length=0;await update({update_id:++id,inline_query:{id:'inline-limit',from:{id:5},query:Array.from({length:9},(_,i)=>`https://x.co/${i}`).join(' ')}});
  const item=calls.find(c=>c.method==='answerInlineQuery').data.results[0];
  assert.equal(item.id,'limit');assert.match(item.input_message_content.message_text,/8 links/);
});
test('undo restores the entire original message and its formatting',async()=>{
  calls.length=0;const chat=-6110,text='📷 Remember this https://instagram.com/reel/FullUndo/?xtok=original';
  const entities=[{type:'bold',offset:3,length:8},{type:'spoiler',offset:3,length:8}];
  await update(message(text,5,chat,{entities}));
  const stored=await db.prepare('SELECT * FROM message_originals WHERE chat_id=?').bind(chat).first();
  assert.ok(stored);assert.equal(JSON.parse(stored.original_json).text,text);
  calls.length=0;await update(message('/undo',5,chat,{reply_to_message:{message_id:stored.bot_msg_id}}));
  const restored=calls.find(c=>c.method==='sendMessage');
  assert.equal(restored.data.text,text);assert.deepEqual(restored.data.entities,entities);
  assert.equal(restored.data.link_preview_options.is_disabled,true);assert.ok(!restored.data.parse_mode);
});
test('undo restores a captioned attachment using its Telegram file ID and spoiler flag',async()=>{
  const chat=-6111,caption='Caption https://instagram.com/reel/CaptionUndo/';
  const caption_entities=[{type:'italic',offset:0,length:7}];
  calls.length=0;await update(message(undefined,5,chat,{caption,caption_entities,photo:[{file_id:'small-photo'},{file_id:'large-photo'}],has_media_spoiler:true}));
  const stored=await db.prepare('SELECT * FROM message_originals WHERE chat_id=?').bind(chat).first();
  calls.length=0;await update(message('/undo',5,chat,{reply_to_message:{message_id:stored.bot_msg_id}}));
  const restored=calls.find(c=>c.method==='sendPhoto');
  assert.equal(restored.data.photo,'large-photo');assert.equal(restored.data.caption,caption);
  assert.deepEqual(restored.data.caption_entities,caption_entities);assert.equal(restored.data.has_spoiler,true);
});
test('undo snapshots are scoped to their original chat and expire after seven days',async()=>{
  const store=new Store(db),stamp=Math.floor(Date.now()/1000);
  await store.record(-6112,991,'https://example.com','Alice',[],5,stamp-8*86400,{original:{text:'old secret'},platform:null,provider:null});
  calls.length=0;await update(message('/undo',5,-6113,{reply_to_message:{message_id:991}}));
  assert.ok(!calls.find(c=>c.method==='sendMessage').data.text.includes('old secret'));
  await store.cleanup(stamp);assert.equal(await store.original(-6112,991),null);
});
test('older rewritten messages retain URL-only undo compatibility',async()=>{
  await db.prepare('INSERT INTO rewritten_messages VALUES(?,?,?,?,?)').bind(-6114,992,'https://example.com/old','Alice',Math.floor(Date.now()/1000)).run();
  calls.length=0;await update(message('/undo',5,-6114,{reply_to_message:{message_id:992}}));
  const sent=calls.find(c=>c.method==='sendMessage');assert.match(sent.data.text,/older post/);assert.match(sent.data.text,/https:\/\/example.com\/old/);
});
test('diagnose redacts query values and does not claim dedup or rate slots',async()=>{
  calls.length=0;const chat=-6120;
  await update(message('/diagnose https://youtube.com/watch?v=privateVideo&t=30&si=privateShare&utm_future=privateCampaign',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');
  assert.match(sent.data.text,/would send/);assert.match(sent.data.text,/Removed parameters:<\/b> si, utm_future/);
  assert.match(sent.data.text,/Retained parameters:<\/b> v, t/);
  assert.ok(!/privateVideo|privateShare|privateCampaign/.test(sent.data.text));
  assert.equal((await db.prepare('SELECT COUNT(*) AS n FROM rate_events WHERE chat_id=?').bind(chat).first()).n,0);
  assert.equal((await db.prepare('SELECT COUNT(*) AS n FROM recent_events WHERE chat_id=?').bind(chat).first()).n,0);
  assert.ok(!diagnosticURL('https://user:password@example.com/a?token=private#secret').includes('password'));
});
test('diagnose explains per-user opt-out, muted senders and forwarded messages',async()=>{
  const raw='https://instagram.com/reel/DiagnoseSkipped/';
  await update(message('/optout',5,-6121));calls.length=0;await update(message('/diagnose '+raw,5,-6121));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/sender opted out/);
  await db.prepare('INSERT INTO blocked_users VALUES(-6122,5)').run();
  calls.length=0;await update(message('/diagnose',7,-6122,{reply_to_message:message(raw,5,-6122)}));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/sender is muted/);
  calls.length=0;await update(message('/diagnose',7,-6123,{reply_to_message:message(raw,5,-6123,{forward_origin:{type:'user'}})}));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/forwarded posts are disabled/);
});
test('diagnose explains disabled platforms, deduplication and active rate limiting',async()=>{
  const raw='https://instagram.com/reel/DiagnoseDedup/';
  await db.prepare("INSERT INTO platform_overrides VALUES(-6124,'instagram',0)").run();
  calls.length=0;await update(message('/diagnose '+raw,5,-6124));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/platform disabled/);
  await update(message(raw,5,-6125));calls.length=0;await update(message('/diagnose '+raw,5,-6125));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/duplicate within/);
  await db.prepare('INSERT INTO chat_settings(chat_id,rate_limit) VALUES(-6126,1)').run();
  await update(message(raw,5,-6126));calls.length=0;await update(message('/diagnose https://instagram.com/reel/NewRateDiagnosis/',5,-6126));
  assert.match(calls.find(c=>c.method==='sendMessage').data.text,/rate limit reached/);
  assert.equal((await db.prepare('SELECT COUNT(*) AS n FROM rate_events WHERE chat_id=-6126').first()).n,1);
});
test('a stored full original is used when diagnosing a rewritten message',async()=>{
  const chat=-6127,text='See https://instagram.com/reel/DiagnoseOriginal/?xtok=private';
  await update(message(text,5,chat));
  const row=await db.prepare('SELECT * FROM message_originals WHERE chat_id=?').bind(chat).first();
  calls.length=0;await update(message('/diagnose',7,chat,{reply_to_message:{message_id:row.bot_msg_id,text:'Shared by Alice',from:{id:123456,is_bot:true}}}));
  const sent=calls.find(c=>c.method==='sendMessage');assert.match(sent.data.text,/xtok/);assert.ok(!sent.data.text.includes('another bot'));
});

// Conservative background health policy: public samples only, never user posts.
const publicCard=()=>new Response('<meta property="og:title" content="Author"><meta property="og:image" content="https://cdn.example/image.jpg">',{headers:{'Content-Type':'text/html'}});
const healthStore=()=>new Store(db);
async function resetHealthAt(platform,provider,stamp) {
  await db.prepare('DELETE FROM provider_health').run();await db.prepare('DELETE FROM provider_probe_cursor').run();
  const start=probePlan().findIndex(p=>p.platform===platform&&p.provider===provider);
  assert.ok(start>=0);await db.prepare('INSERT INTO provider_probe_cursor VALUES(1,?,?)').bind(start,Math.floor(stamp/3600)-1).run();
}
test('three corroborated public-content failures are required before a temporary cooldown',async()=>{
  const stamp=Math.floor(Date.now()/1000)-7200,store=healthStore();await resetHealthAt('instagram','vx',stamp);
  const plan=probePlan(),start=plan.findIndex(p=>p.platform==='instagram'&&p.provider==='vx');
  const net=async url=>new URL(url).hostname==='vxinstagram.com'?new Response('',{status:404}):publicCard();
  for(let n=0;n<3;n++) {
    if(n)await db.prepare('UPDATE provider_probe_cursor SET cursor=?').bind(start).run();
    await runHealthChecks(store,{net,stamp:stamp+n*3600,batchSize:1});
    const row=await db.prepare("SELECT * FROM provider_health WHERE platform='instagram' AND provider='vx'").first();
    assert.equal(row.failures,n+1);assert.equal(quarantined(row,stamp+n*3600),n===2);
  }
  const row=await db.prepare("SELECT * FROM provider_health WHERE platform='instagram' AND provider='vx'").first();
  assert.equal(row.cooldown_until,stamp+7200+6*3600);
  await db.prepare('DELETE FROM provider_health').run();
});
test('403s, unconfirmed failures and profile observations cannot quarantine providers',async()=>{
  const stamp=Math.floor(Date.now()/1000),store=healthStore();
  for(const kind of ['blocked','all-failed','profile']) {
    const platform=kind==='profile'?'facebook':'instagram',provider=kind==='profile'?'bed':'vx';
    await resetHealthAt(platform,provider,stamp);
    const index=probePlan().findIndex(p=>p.platform===platform&&p.provider===provider);
    for(let n=0;n<3;n++) {
      if(n)await db.prepare('UPDATE provider_probe_cursor SET cursor=?').bind(index).run();
      await runHealthChecks(store,{net:async()=>new Response('',{status:kind==='blocked'?403:404}),stamp:stamp+n*3600,batchSize:1});
    }
    const row=await db.prepare('SELECT * FROM provider_health WHERE platform=? AND provider=?').bind(platform,provider).first();
    assert.equal(row.failures,0);assert.equal(row.cooldown_until,0);
  }
  await db.prepare('DELETE FROM provider_health').run();
});
test('healthy samples recover a provider and repeated cron delivery is idempotent',async()=>{
  const stamp=Math.floor(Date.now()/1000),store=healthStore();await resetHealthAt('instagram','vx',stamp);
  await db.prepare("INSERT INTO provider_health VALUES('instagram','vx',3,?,?,0,404,'confirmed_sample_failure')").bind(stamp+3600,stamp-3600).run();
  let count=0;const net=async()=>{count++;return publicCard();};
  await runHealthChecks(store,{net,stamp,batchSize:1});const firstCount=count;
  const row=await db.prepare("SELECT * FROM provider_health WHERE platform='instagram' AND provider='vx'").first();
  assert.equal(row.failures,0);assert.equal(row.cooldown_until,0);assert.equal(row.last_success_at,stamp);
  assert.equal((await runHealthChecks(store,{net,stamp,batchSize:1})).checked,0);assert.equal(count,firstCount);
  await db.prepare('DELETE FROM provider_health').run();
});
test('health-based selection respects explicit fallback-off and no-account browser preferences',async()=>{
  const stamp=Math.floor(Date.now()/1000),row={cooldown_until:stamp+3600,checked_at:stamp};
  const health={twitter:{vx:row},instagram:{ee:row}};
  const fallback=await fixLink('https://instagram.com/reel/HealthFallback/',{}, {},{},fetch,false,health);
  assert.notEqual(fallback.preview,'https://eeinstagram.com/reel/HealthFallback/');
  const forced=await fixLink('https://instagram.com/reel/HealthForced/',{provider_fallback:0},{},{},fetch,false,health);
  assert.equal(forced.preview,'https://eeinstagram.com/reel/HealthForced/');
  const browser=await fixLink('https://twitter.com/a/status/1',{}, {twitter:'xcancel'},{},fetch,false,health);
  assert.equal(browser.url,'https://xcancel.com/a/status/1');assert.notEqual(browser.preview,'https://vxtwitter.com/a/status/1');
  assert.equal(pickHealthy('instagram','ee',{ee:{...row,cooldown_until:stamp-1}},stamp),'ee');
});
test('runtime avoids quarantined previews and retry skips them without changing saved settings',async()=>{
  const stamp=Math.floor(Date.now()/1000),chat=-6130;
  await db.prepare('DELETE FROM provider_health').run();
  await db.prepare("INSERT INTO provider_health VALUES('instagram','ee',3,?,?,0,404,'confirmed_sample_failure')").bind(stamp+3600,stamp).run();
  calls.length=0;await update(message('https://instagram.com/reel/RuntimeHealth/',5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');assert.ok(sent);assert.ok(!sent.data.link_preview_options.url.includes('eeinstagram.com'));
  calls.length=0;await update({update_id:++id,callback_query:{id:'skip-health',from:{id:5},data:'e:instagram:1',message:{message_id:100,chat:{id:chat,type:'supergroup'},text:'https://instagram.com/reel/RuntimeHealth/'}}});
  assert.ok(!calls.find(c=>c.method==='editMessageText').data.link_preview_options.url.includes('eeinstagram.com'));
  assert.equal(await db.prepare('SELECT * FROM provider_settings WHERE chat_id=?').bind(chat).first(),null);
  await db.prepare('DELETE FROM provider_health').run();
});
test('probe response reads are bounded and external redirects are never followed',async()=>{
  let cancelled=false;
  const body=new ReadableStream({start(c){c.enqueue(new TextEncoder().encode('<meta property="og:video" content="https://cdn.example/v.mp4">'+'x'.repeat(200000)));},cancel(){cancelled=true;}});
  const result=await probeURL('https://eeinstagram.com/reel/Test',async()=>new Response(body,{headers:{'Content-Type':'text/html'}}));
  assert.equal(result.kind,'success');assert.equal(cancelled,true);
  let callsCount=0;const redirect=await probeURL('https://eeinstagram.com/reel/Test',async()=>{callsCount++;return new Response(null,{status:302,headers:{location:'http://127.0.0.1/private'}});});
  assert.equal(redirect.kind,'uncertain');assert.equal(callsCount,1);
  assert.equal(usableMetadata('<meta property="og:title" content="Log in"><meta property="og:image" content="logo.jpg">'),false);
});
test('all configured platforms have a public observation or content sample and no private input is persisted in health state',()=>{
  for(const platform of Object.keys(PROVIDERS))assert.ok(CONTENT_SAMPLES[platform]||OBSERVATION_SAMPLES[platform]);
  assert.ok(probePlan().every(p=>p.provider!=='native'&&!Object.hasOwn(PROVIDERS[p.platform].noauth_embed??{},p.provider)));
});

test('oversized spoiler links keep the original and return a non-revealing explanation',async()=>{
  const prefix='http://youtube.com/watch?v=abc&list=';
  const text=prefix+'z'.repeat(4096-prefix.length);
  calls.length=0;await update(message(text,5,-6140,{entities:[{type:'spoiler',offset:0,length:text.length}]}));
  const sent=calls.find(c=>c.method==='sendMessage');assert.ok(sent);
  assert.match(sent.data.text,/original message was kept/);
  assert.ok(!sent.data.text.includes('youtube.com'));assert.equal(sent.data.link_preview_options.is_disabled,true);
  assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
});
test('snapshot storage failure preserves the original after a confirmed replacement',async()=>{
  await db.prepare('DROP TABLE message_originals').run();
  try {
    calls.length=0;const {response,body}=await update(message('https://instagram.com/reel/StorageFailure/',5,-6141));
    assert.equal(response.status,200);assert.equal(calls.filter(c=>c.method==='sendMessage').length,1);
    assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
    assert.equal((await db.prepare('SELECT state FROM deliveries WHERE update_id=?').bind(body.update_id).first()).state,'delivered');
  }finally {
    const migration=await readFile(new URL('../migrations/0002-improvements.sql',import.meta.url),'utf8');
    for(const sql of migration.split(';').map(s=>s.trim()).filter(Boolean))await db.prepare(sql).run();
  }
});

// 2.2: durable post controls and edit synchronisation.
const click=async(sent,chat,data,user=5)=>update({update_id:++id,callback_query:{id:'post-'+id,from:{id:user},data,
  message:{message_id:sent.botId,chat:{id:chat,type:'supergroup'},text:sent.text??'Shared by Alice'}}});
async function createPost(text,chat,extra={}) {
  calls.length=0;const source=message(text,5,chat,extra);await update(source);
  const send=calls.find(c=>c.method==='sendMessage');assert.ok(send);
  const row=await db.prepare('SELECT * FROM post_controls WHERE chat_id=? AND source_msg_id=?').bind(chat,source.message_id).first();
  assert.ok(row);return {source,botId:row.bot_msg_id,text:send.data.text,keyboard:send.data.reply_markup,post:JSON.parse(row.state_json)};
}
test('retry history tries each backend once and explains exhaustion across webhook requests',async()=>{
  const chat=-7001,sent=await createPost('https://x.com/a/status/RetryHistory',chat);
  const seen=new Set([sent.post.links[0].previewKey]);
  for(let n=0;n<Object.keys(PROVIDERS.twitter.options).length+1;n++) {
    const row=await new Store(db).post(chat,sent.botId),post=JSON.parse(row.state_json);
    calls.length=0;await click(sent,chat,`e:twitter:0:${hash(linkIdentityForTest(post.links[0].url,'twitter')).slice(0,12)}`);
    const edited=calls.find(c=>c.method==='editMessageText');
    if(!edited){assert.match(calls.find(c=>c.method==='answerCallbackQuery').data.text,/All available.*tried/);break;}
    const next=JSON.parse((await new Store(db).post(chat,sent.botId)).state_json).links[0].previewKey;
    assert.ok(!seen.has(next),`Repeated backend ${next}`);seen.add(next);
  }
  assert.equal(seen.size,new Set(Object.keys(PROVIDERS.twitter.options).map(k=>PROVIDERS.twitter.noauth_embed?.[k]??k)).size);
  calls.length=0;await click(sent,chat,'e:twitter:0');assert.ok(!calls.some(c=>c.method==='editMessageText'));
});
function linkIdentityForTest(url,p) {const u=new URL(stripTracking(url,p));return u.pathname+u.search+u.hash;}
test('multi-link preview selection is sender/admin-only and retains full text and formatting',async()=>{
  const chat=-7002,text='Compare https://x.com/a/status/ChoosePreview and https://instagram.com/reel/ChoosePreview/';
  const sent=await createPost(text,chat,{entities:[{type:'bold',offset:0,length:7}]});
  const choices=sent.keyboard.inline_keyboard.flat().filter(b=>b.callback_data.startsWith('p:'));assert.equal(choices.length,2);
  calls.length=0;await click(sent,chat,choices[1].callback_data,6);
  assert.ok(!calls.some(c=>c.method==='editMessageText'));assert.match(calls.find(c=>c.method==='answerCallbackQuery').data.text,/original sender/);
  calls.length=0;await click(sent,chat,choices[1].callback_data,5);
  const edited=calls.find(c=>c.method==='editMessageText');assert.match(edited.data.link_preview_options.url,/eeinstagram/);assert.match(edited.data.text,/<b>Compare<\/b>/);assert.match(edited.data.text,/x.com/);assert.match(edited.data.text,/instagram.com/);
  calls.length=0;await click(sent,chat,choices[0].callback_data,7);assert.match(calls.find(c=>c.method==='editMessageText').data.link_preview_options.url,/vxtwitter/);
});
test('an outdated multi-link selector cannot change an edited post',async()=>{
  const chat=-7003,sent=await createPost('https://x.com/a/status/StaleChoice https://instagram.com/reel/StaleChoice/',chat);
  const stale=sent.keyboard.inline_keyboard.flat().find(b=>b.callback_data.startsWith('p:1:')).callback_data;
  await update({update_id:++id,edited_message:{...sent.source,text:'https://instagram.com/reel/ChangedChoice/',edit_date:100}});
  calls.length=0;await click(sent,chat,stale);assert.ok(!calls.some(c=>c.method==='editMessageText'));assert.match(calls.find(c=>c.method==='answerCallbackQuery').data.text,/outdated/);
});
test('caption edits update the existing repost, retain thread/formatting and refresh undo without extra stats',async()=>{
  const chat=-7004,sent=await createPost(undefined,chat,{caption:'First https://instagram.com/reel/EditCaption/?dlrf=private',photo:[{file_id:'edit-photo'}],message_thread_id:42});
  const before=await db.prepare('SELECT SUM(count) n FROM chat_stats WHERE chat_id=?').bind(chat).first();
  calls.length=0;await update({update_id:++id,edited_message:{...sent.source,caption:'Updated https://instagram.com/reel/EditCaption/?dlrf=private',caption_entities:[{type:'italic',offset:0,length:7}],edit_date:100}});
  assert.equal(calls.filter(c=>c.method==='editMessageText').length,1);assert.equal(calls.filter(c=>c.method==='sendMessage').length,0);assert.equal(calls.filter(c=>c.method==='deleteMessage').length,0);
  const edited=calls.find(c=>c.method==='editMessageText');assert.equal(edited.data.message_id,sent.botId);assert.match(edited.data.text,/<i>Updated<\/i>/);assert.ok(!edited.data.text.includes('dlrf'));
  assert.deepEqual(await db.prepare('SELECT SUM(count) n FROM chat_stats WHERE chat_id=?').bind(chat).first(),before);
  calls.length=0;await update(message('/undo',5,chat,{reply_to_message:{message_id:sent.botId}}));
  const undo=calls.find(c=>c.method==='sendPhoto');assert.equal(undo.data.photo,'edit-photo');assert.match(undo.data.caption,/^Updated/);assert.equal(undo.data.caption_entities[0].type,'italic');
});
test('text edits after deletion denial use the same repost and skip duplicate/rate reservations',async()=>{
  const chat=-7005;deleteFail=true;const sent=await createPost('https://x.com/a/status/EditText',chat);deleteFail=false;
  const rates=await db.prepare('SELECT COUNT(*) n FROM rate_events WHERE chat_id=?').bind(chat).first();
  calls.length=0;await update({update_id:++id,edited_message:{...sent.source,text:'Changed https://x.com/a/status/EditText',edit_date:100}});
  assert.equal(calls.filter(c=>c.method==='editMessageText').length,1);assert.ok(!calls.some(c=>c.method==='sendMessage'));
  assert.deepEqual(await db.prepare('SELECT COUNT(*) n FROM rate_events WHERE chat_id=?').bind(chat).first(),rates);
});
test('removing all links edits the repost and removes the old preview and controls',async()=>{
  const chat=-7006,sent=await createPost('https://x.com/a/status/RemovedLink',chat);
  calls.length=0;await update({update_id:++id,edited_message:{...sent.source,text:'Link removed',edit_date:100}});
  const edited=calls.find(c=>c.method==='editMessageText');assert.equal(edited.data.text,'Link removed');assert.equal(edited.data.link_preview_options.is_disabled,true);assert.deepEqual(edited.data.reply_markup.inline_keyboard,[]);
});
test('older edit timestamps cannot overwrite a newer edit or its undo snapshot',async()=>{
  const chat=-7007,sent=await createPost('https://x.com/a/status/EditOrder',chat);
  await update({update_id:++id,edited_message:{...sent.source,text:'New https://x.com/a/status/EditOrder',edit_date:200}});
  calls.length=0;await update({update_id:++id,edited_message:{...sent.source,text:'Old https://x.com/a/status/EditOrder',edit_date:100}});
  assert.ok(!calls.some(c=>c.method==='editMessageText'));assert.match(JSON.parse((await new Store(db).original(chat,sent.botId)).original_json).text,/^New/);
});
test('adding a spoiler on edit disables previews and buttons; forged retry cannot reveal it',async()=>{
  const chat=-7008,url='https://instagram.com/reel/EditSpoiler/',sent=await createPost(url,chat);
  calls.length=0;await update({update_id:++id,edited_message:{...sent.source,entities:[{type:'spoiler',offset:0,length:url.length}],edit_date:100}});
  const edited=calls.find(c=>c.method==='editMessageText');assert.equal(edited.data.link_preview_options.is_disabled,true);assert.deepEqual(edited.data.reply_markup.inline_keyboard,[]);
  calls.length=0;await click(sent,chat,'e:instagram:0');assert.ok(!calls.some(c=>c.method==='editMessageText'));assert.match(calls[0].data.text,/spoiler/);
});
test('post controls enforce chat scoping, expiry and a per-post edit lease',async()=>{
  const chat=-7009,sent=await createPost('https://x.com/a/status/EditLease',chat),store=new Store(db),now=Math.floor(Date.now()/1000);
  assert.equal(await store.post(chat-1,sent.botId),null);assert.equal(await store.sourcePost(chat-1,sent.source.message_id),null);
  assert.equal(await store.lockPost(chat,sent.botId,now),true);assert.equal(await store.lockPost(chat,sent.botId,now),false);
  calls.length=0;await click(sent,chat,'e:twitter:0');assert.match(calls[0].data.text,/in progress/);assert.ok(!calls.some(c=>c.method==='editMessageText'));await store.unlockPost(chat,sent.botId);
  await db.prepare('UPDATE post_controls SET ts=? WHERE chat_id=?').bind(now-8*86400,chat).run();assert.equal(await store.post(chat,sent.botId),null);
  await store.cleanup(now);assert.equal(await db.prepare('SELECT * FROM post_controls WHERE chat_id=?').bind(chat).first(),null);
});
test('inline multi-link results let the sender select each preview without losing surrounding text',async()=>{
  calls.length=0;await update({update_id:++id,inline_query:{id:'inline-choice',from:{id:5},query:'Compare https://x.com/a/status/InlineChoice with https://instagram.com/reel/InlineChoice/ please.'}});
  const results=calls.find(c=>c.method==='answerInlineQuery').data.results;assert.equal(results.length,2);assert.notEqual(results[0].input_message_content.link_preview_options.url,results[1].input_message_content.link_preview_options.url);assert.equal(results[0].input_message_content.message_text,results[1].input_message_content.message_text);assert.match(results[1].input_message_content.message_text,/Compare.*please/);
});

const sanitisationCases=JSON.parse(await readFile(new URL('./fixtures/sanitisation.json',import.meta.url),'utf8'));
test('sanitisation fixture coverage matches every configured platform',()=>assert.deepEqual(new Set(sanitisationCases.map(c=>c.platform)),new Set(Object.keys(PROVIDERS))));
for(const fixture of sanitisationCases)test('sanitisation corpus: '+fixture.name,async()=>{
  const noNetwork=async()=>new Response(null,{status:200});
  const fixed=await fixLink(fixture.input,{}, {},{weibo:1},noNetwork);
  assert.equal(fixed.url,fixture.expected);
  const again=await fixLink(fixed.url,{}, {},{weibo:1},noNetwork);assert.equal(again.url,fixture.expected);
  for(const key of Object.keys(PROVIDERS[fixture.platform].options)) {
    const configured=await fixLink(fixture.input,{}, {[fixture.platform]:key},{weibo:1},noNetwork);
    assert.ok(!configured.url.includes('secret'));assert.ok(!configured.preview.includes('secret'));
    const expected=new URL(fixture.expected),preview=new URL(configured.preview);
    assert.equal(preview.pathname,expected.pathname);assert.equal(preview.search,expected.search);assert.equal(preview.hash,expected.hash);
    if(!Object.hasOwn(PROVIDERS[fixture.platform].noauth_embed??{},key)) {
      const pasted=await fixLink(configured.preview,{}, {},{weibo:1},noNetwork);
      // Pasted proxy URLs normalise to the first official host (X has two).
      assert.equal(new URL(pasted.url).pathname,expected.pathname);assert.equal(new URL(pasted.url).search,expected.search);
    }
  }
});
for(const [name,type,me,member,info,expect] of [
  ['ordinary group member','supergroup',{}, {status:'member'}, {permissions:{can_send_messages:true,can_add_web_page_previews:false}}, [/Read all group messages: no/,/Add previews: no/,/BotFather/,/Delete messages/]],
  ['administrator','supergroup',{}, {status:'administrator',can_delete_messages:true},{}, [/Read all group messages: yes/,/Delete originals: yes/,/Add previews: yes/]],
  ['privacy-disabled member','supergroup',{can_read_all_group_messages:true},{status:'member'},{permissions:{can_send_messages:true,can_add_web_page_previews:true}}, [/Read all group messages: yes/,/Delete originals: no/]],
  ['restricted member','supergroup',{}, {status:'restricted',can_send_messages:false,can_add_web_page_previews:false},{}, [/Send messages: no/,/Allow “Send messages”/]],
  ['channel administrator without post rights','channel',{}, {status:'administrator',can_post_messages:false,can_delete_messages:true},{}, [/Send messages: no/,/Post messages/]],
  ['private chat','private',{},null,null,[/private chat/,/this reply/]],
])test('status capability guidance: '+name,async()=>{
  const tg={call:async method=>method==='getMe'?{id:123,...me}:method==='getChatMember'?member:info};
  const text=await permissionStatus({chat:{id:-1,type}},tg);for(const pattern of expect)assert.match(text,pattern);
});
test('status reports unavailable permissions without pretending checks passed',async()=>{
  const text=await permissionStatus({chat:{id:-1,type:'supergroup'}},{call:async method=>{if(method==='getMe')return{id:123};throw new Error('unavailable');}});
  assert.match(text,/unavailable/);assert.ok(!text.includes('Read all group messages: yes'));
});

test('an unchanged generic URL remains selectable alongside a fixed social link',async()=>{
  const chat=-7010,sent=await createPost('Read https://example.com/article then https://instagram.com/reel/GenericChoice/',chat);
  assert.equal(sent.post.links.length,2);assert.equal(sent.post.preview_index,1);
  calls.length=0;await click(sent,chat,sent.keyboard.inline_keyboard.flat().find(b=>b.callback_data.startsWith('p:0:')).callback_data);
  const edited=calls.find(c=>c.method==='editMessageText');assert.equal(edited.data.link_preview_options.url,'https://example.com/article');assert.ok(!edited.data.reply_markup.inline_keyboard.flat().some(b=>b.callback_data.startsWith('e:')));
});
test('manual retry preserves an explicitly selected browser frontend through multiple backends',async()=>{
  const chat=-7011;await new Store(db).choose(chat,'twitter','xcancel');
  const sent=await createPost('https://twitter.com/a/status/BrowserPreserve',chat);
  for(let n=0;n<2;n++){calls.length=0;await click(sent,chat,'e:twitter:0');const post=JSON.parse((await new Store(db).post(chat,sent.botId)).state_json);assert.equal(new URL(post.links[0].url).hostname,'xcancel.com');}
});
test('an edit from a different sender cannot overwrite the original author snapshot',async()=>{
  const chat=-7012,sent=await createPost('https://x.com/a/status/SenderCheck',chat);
  calls.length=0;await update({update_id:++id,edited_message:{...sent.source,from:{id:6,first_name:'Other'},text:'Changed https://x.com/a/status/SenderCheck',edit_date:300}});
  assert.ok(!calls.some(c=>c.method==='editMessageText'));assert.equal(JSON.parse((await new Store(db).original(chat,sent.botId)).original_json).user_id,5);
});
test('an edited channel post updates its existing repost without sending a duplicate',async()=>{
  const chat=-7013,source=message('https://x.com/a/status/ChannelEdit',5,chat,{chat:{id:chat,type:'channel'}});
  calls.length=0;await update({update_id:++id,channel_post:source});
  const row=await new Store(db).sourcePost(chat,source.message_id);assert.ok(row);
  calls.length=0;await update({update_id:++id,edited_channel_post:{...source,text:'Changed https://x.com/a/status/ChannelEdit',edit_date:100}});
  assert.equal(calls.filter(c=>c.method==='editMessageText').length,1);assert.ok(!calls.some(c=>c.method==='sendMessage'));assert.equal(calls[0].data.message_id,row.bot_msg_id);
});

test('rejected source edits never send a duplicate or advance the stored snapshot',async()=>{
  const chat=-7014,sent=await createPost('https://x.com/a/status/RejectEdit',chat);
  calls.length=0;editFailure={code:400};
  try {
    await update({update_id:++id,edited_message:{...sent.source,text:'Changed https://x.com/a/status/RejectEdit',edit_date:100}});
    assert.equal(calls.filter(c=>c.method==='editMessageText').length,2);assert.ok(!calls.some(c=>c.method==='sendMessage'));
    const row=await new Store(db).post(chat,sent.botId);assert.equal(row.lock_until,0);assert.equal(JSON.parse(row.state_json).original.text,sent.source.text);
  } finally {editFailure=null;}
});
test('spoiler-safe source edits retain native entities when Telegram rejects HTML',async()=>{
  const chat=-7015,url='https://instagram.com/reel/EditedFallback/',sent=await createPost(url,chat);
  calls.length=0;editFailure={code:400,once:true};
  try {
    await update({update_id:++id,edited_message:{...sent.source,entities:[{type:'spoiler',offset:0,length:url.length}],edit_date:100}});
    const edits=calls.filter(c=>c.method==='editMessageText');assert.equal(edits.length,2);assert.equal(edits[1].data.parse_mode,undefined);assert.ok(edits[1].data.entities.some(e=>e.type==='spoiler'));assert.equal(edits[1].data.link_preview_options.is_disabled,true);assert.ok(!calls.some(c=>c.method==='sendMessage'));
  } finally {editFailure=null;}
});
test('new post controls and source snapshots share the initial seven-day retention window',async()=>{
  const chat=-7016,sent=await createPost('https://x.com/a/status/Retention',chat);
  const before=await new Store(db).post(chat,sent.botId);
  await update({update_id:++id,edited_message:{...sent.source,text:'Edit https://x.com/a/status/Retention',edit_date:100}});
  assert.equal((await new Store(db).post(chat,sent.botId)).ts,before.ts);
  assert.equal((await new Store(db).original(chat,sent.botId)).ts,before.ts);
});

// 2.2.1: Reddit share attribution must not survive in clickable destinations.
const redditScreenshot='https://www.reddit.com/r/IndiaTodayLIVE/comments/1xtbamu/two_men_posing_as_customers_allegedly_stole_a/';
test('Reddit share_id cleanup is case-insensitive, repeated-key safe and platform-scoped',async()=>{
  assert.equal(stripTracking(redditScreenshot+'?share_id=one&SHARE_ID=two&context=3&sort=new#comment'),redditScreenshot+'?context=3&sort=new#comment');
  assert.equal(stripTracking('https://example.com/post?share_id=needed'),'https://example.com/post?share_id=needed');
  assert.equal((await fixLink(redditScreenshot+'?share_id=secret',{}, {},{reddit:0})).url,redditScreenshot+'?share_id=secret');
});
test('Reddit screenshot link is clean in attribution, previews, /clean and inline results',async()=>{
  const chat=-7101,raw=redditScreenshot+'?share_id=secret';calls.length=0;await update(message(raw,5,chat));
  const sent=calls.find(c=>c.method==='sendMessage');assert.ok(!JSON.stringify(sent.data).includes('share_id'));assert.match(sent.data.text,/href="https:\/\/www.reddit.com/);
  calls.length=0;await update(message('/clean '+raw,5,chat));assert.ok(!calls.find(c=>c.method==='sendMessage').data.text.includes('share_id'));
  calls.length=0;await update({update_id:++id,inline_query:{id:'reddit-clean',from:{id:5},query:raw}});assert.ok(!JSON.stringify(calls.find(c=>c.method==='answerInlineQuery').data.results).includes('share_id'));
});
for(const exhausted of [false,true])test('retry cleans stored Reddit targets from before the fix; exhausted='+exhausted,async()=>{
  const chat=exhausted?-7103:-7102,sent=await createPost(redditScreenshot,chat),store=new Store(db);
  const row=await store.post(chat,sent.botId),post=JSON.parse(row.state_json),link=post.links[0];
  link.url=redditScreenshot+'?share_id=old';link.preview='https://vxreddit.com'+new URL(link.url).pathname+'?share_id=old';link.original=link.url;link.raw=link.url;
  post.original.text=link.url;
  const oldKey='reddit:'+new URL(link.url).pathname+'?share_id=old';
  post.tried={[oldKey]:exhausted?Object.keys(PROVIDERS.reddit.options).map(k=>PROVIDERS.reddit.noauth_embed?.[k]??k):['vx']};
  await store.savePost(chat,sent.botId,row.source_msg_id,row.user_id,post,row.ts);
  const fingerprint=hash(new URL(link.url).pathname+'?share_id=old').slice(0,12);
  calls.length=0;await click(sent,chat,'e:reddit:1:'+fingerprint);
  const edited=calls.find(c=>c.method==='editMessageText');assert.ok(edited);assert.ok(!JSON.stringify(edited.data).includes('share_id'));
  const updated=JSON.parse((await store.post(chat,sent.botId)).state_json);assert.ok(!updated.links[0].url.includes('share_id'));assert.match(updated.original.text,/share_id=old/);
  const key='reddit:'+new URL(link.url).pathname;assert.ok(updated.tried[key].includes('vx'));assert.equal(updated.tried[oldKey],undefined);
  if(exhausted)assert.match(calls.find(c=>c.method==='answerCallbackQuery').data.text,/Tracking removed.*tried/);
});
