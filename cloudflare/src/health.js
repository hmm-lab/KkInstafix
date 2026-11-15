import {PROVIDERS} from './config.js';
import {applyProvider} from './links.js';

export const COOLDOWN_SECONDS=6*3600;
export const FAILURE_THRESHOLD=3;
export const PROBE_BATCH_SIZE=4;
// Only public, curated examples. Never probe posts from user messages.
export const CONTENT_SAMPLES={
  instagram:['https://instagram.com/reel/C6bfaFzIqqR/','https://instagram.com/p/DKMv_h9o_Oj/?img_index=2'],
  youtube:['https://www.youtube.com/watch?v=dQw4w9WgXcQ','https://www.youtube.com/watch?v=CpJSgoOD1-Y'],
  twitter:['https://twitter.com/jack/status/20'],
  tiktok:['https://www.tiktok.com/@mxmtoon/video/7354154112285527339'],
  bluesky:['https://bsky.app/profile/bsky.app/post/3n22yg6lg2k2f','https://bsky.app/profile/damjef.bsky.social/post/3mzsgbnati22w'],
};
// These are observation-only samples; landing/profile pages cannot justify a quarantine.
export const OBSERVATION_SAMPLES={
  reddit:'https://reddit.com/r/announcements/',facebook:'https://facebook.com/NASA',threads:'https://threads.com/@zuck',
  piviv:'https://pixiv.net/en',tumblr:'https://tumblr.com/staff',bilibili:'https://bilibili.com/video/BV1xx411c7mD',
  snapchat:'https://snapchat.com/add/team.snapchat',spotify:'https://open.spotify.com/track/4PTG3Z6ehGkBFwjybzWkR8',
  twitch:'https://twitch.tv/nasa',ifunny:'https://ifunny.co/',furaffinity:'https://furaffinity.net/user/fender/',
  deviantart:'https://deviantart.com/team',dribbble:'https://dribbble.com/dribbble',kick:'https://kick.com/xqc',
  weibo:'https://weibo.com/rmrb',xiaohongshu:'https://xhslink.com/',pinterest:'https://pinterest.com/',
};
export {quarantined,pickHealthy,nextHealthy,healthLabel} from './provider-policy.js';
async function prefix(stream,limit=8192) {
  if(!stream)return {body:'',truncated:false};
  const reader=stream.getReader(),parts=[];let size=0;
  try {while(size<limit){const {done,value}=await reader.read();if(done)break;const part=value.subarray(0,limit-size);parts.push(part);size+=part.length;}
    if(size>=limit)await reader.cancel();}
  finally{reader.releaseLock();}
  const data=new Uint8Array(size);let at=0;for(const p of parts){data.set(p,at);at+=p.length;}
  return {body:new TextDecoder().decode(data),truncated:size>=limit};
}
const attr=(tag,name)=>new RegExp('\\b'+name+'\\s*=\\s*(?:"([^"]*)"|\'([^\']*)\'|([^\\s>]+))','i').exec(tag)?.slice(1).find(v=>v!==undefined)??'';
export function usableMetadata(body,type='text/html') {
  if(/^(video|image|audio)\//i.test(type))return true;
  const values={};for(const tag of body.match(/<meta\b[^>]*>/gi)??[]) {
    const key=(attr(tag,'property')||attr(tag,'name')).toLowerCase();values[key]=attr(tag,'content');
  }
  const title=values['og:title']||values['twitter:title']||'';
  if(/^(?:fxinstagram|embed fixer|embed fixes|embedez)$/i.test(title)&&!values['og:video']&&!values['og:video:url'])return false;
  if(/log\s*in|sign\s*up|not found|unavailable|access denied|something went wrong|^notice$/i.test(title))return false;
  return !!((title&&(values['og:image']||values['og:image:url']||values['twitter:image']||values['og:description']||values['twitter:description']))||values['og:video']||values['og:video:url']||values['twitter:player:stream']);
}
export async function probeURL(url,net=fetch) {
  let current=url;
  for(let hop=0;hop<2;hop++) {
    try {
      const response=await net(current,{redirect:'manual',headers:{'User-Agent':'TelegramBot (like TwitterBot)'},signal:AbortSignal.timeout(2500)});
      const status=response.status;
      if(status>=300&&status<400) {
        await response.body?.cancel();
        const next=new URL(response.headers.get('location')??'',current);
        if(next.protocol==='https:'&&!next.username&&!next.password&&next.hostname.replace(/^www\./,'')===new URL(url).hostname.replace(/^www\./,'')&&hop===0){current=next.href;continue;}
        return {status,kind:'uncertain',evidence:'redirect_needs_review'};
      }
      if([401,403,429].includes(status)){await response.body?.cancel();return {status,kind:'uncertain',evidence:'access_blocked_or_limited'};}
      if(status!==200){await response.body?.cancel();return {status,kind:'failure',evidence:'http_error'};}
      const type=response.headers.get('Content-Type')??'';
      if(/^(image|video|audio)\//i.test(type)){await response.body?.cancel();return {status,kind:'success',evidence:'content_metadata'};}
      const {body,truncated}=await prefix(response.body);
      return usableMetadata(body,type)?{status,kind:'success',evidence:'content_metadata'}:truncated?{status,kind:'uncertain',evidence:'metadata_prefix_truncated'}:{status,kind:'failure',evidence:'no_usable_metadata'};
    }catch{return {status:null,kind:'uncertain',evidence:'network_or_timeout'};}
  }
  return {status:null,kind:'uncertain',evidence:'redirect_needs_review'};
}
export const probePlan=()=>Object.entries(PROVIDERS).flatMap(([platform,cfg])=>Object.keys(cfg.options)
  .filter(key=>key!=='native'&&!Object.hasOwn(cfg.noauth_embed??{},key)).map(provider=>({platform,provider})));
export async function runHealthChecks(store,{net=fetch,stamp=Math.floor(Date.now()/1000),batchSize=PROBE_BATCH_SIZE}={}) {
  const plan=probePlan();
  const lease=await store.stmt(`INSERT INTO provider_probe_cursor VALUES(1,?,?) ON CONFLICT(id)
    DO UPDATE SET cursor=provider_probe_cursor.cursor+?,slot=excluded.slot WHERE provider_probe_cursor.slot<excluded.slot RETURNING cursor`,batchSize,Math.floor(stamp/3600),batchSize).first();
  if(!lease)return {checked:0};
  const oldRows=(await store.stmt('SELECT * FROM provider_health').all()).results;
  const statements=[];
  for(let n=0;n<Math.min(batchSize,plan.length);n++) {
    const item=plan[(lease.cursor-batchSize+n)%plan.length],cfg=PROVIDERS[item.platform];
    const curated=CONTENT_SAMPLES[item.platform],samples=curated??[OBSERVATION_SAMPLES[item.platform]??'https://'+cfg.domains[0]+'/'];
    const results=[];
    for(const raw of samples)results.push(await probeURL(applyProvider(raw,item.platform,item.provider),net));
    const previous=oldRows.find(r=>r.platform===item.platform&&r.provider===item.provider);
    let failures=previous?.failures??0,cooldown=previous?.cooldown_until??0,lastSuccess=previous?.last_success_at??0;
    let evidence='sample_needs_review';
    if(curated&&results.some(r=>r.kind==='success')){failures=0;cooldown=0;lastSuccess=stamp;evidence='content_metadata';}
    else if(curated&&results.length>=2&&results.every(r=>r.kind==='failure')) {
      const control=Object.keys(cfg.options).find(k=>k!==item.provider&&!Object.hasOwn(cfg.noauth_embed??{},k));
      const controls=[];if(control)for(const raw of samples)controls.push(await probeURL(applyProvider(raw,item.platform,control),net));
      if(controls.length===samples.length&&controls.every(r=>r.kind==='success')) {
        failures=(previous?.checked_at>stamp-48*3600?failures:0)+1;evidence='confirmed_sample_failure';
        if(failures>=FAILURE_THRESHOLD)cooldown=stamp+COOLDOWN_SECONDS;
      }else evidence='control_inconclusive';
    }else if(!curated)evidence=results.some(r=>r.kind==='success')?'observation_only':'sample_needs_review';
    else evidence=results.find(r=>r.kind==='uncertain')?.evidence??'sample_needs_review';
    statements.push(store.stmt('INSERT OR REPLACE INTO provider_health VALUES(?,?,?,?,?,?,?,?)',item.platform,item.provider,failures,cooldown,stamp,lastSuccess,results[0]?.status??null,evidence));
  }
  if(statements.length)await store.db.batch(statements);
  await store.cache?.remove('health','all');
  console.log(JSON.stringify({event:'provider_health_batch',checked:statements.length}));
  return {checked:statements.length};
}
