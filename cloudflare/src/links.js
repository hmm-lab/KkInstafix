import {pickHealthy} from './provider-policy.js';
import { PROVIDERS, TRACKING, PLATFORM_TRACKING, INSTAGRAM_CONTENT_QUERY, INSTAGRAM_CONTENT_PATH, GENERIC_TRACKING, YOUTUBE_HOSTS,
  YOUTUBE_TRACKING, AMAZON_TLDS, AMAZON_TRACKING, EBAY_TLDS, EBAY_TRACKING,
  ALIEXPRESS_DOMAINS, ALIEXPRESS_TRACKING, LINKEDIN_TRACKING, PINTEREST_DOMAINS,
  PINTEREST_TRACKING, APPLE_MUSIC_TRACKING, VIMEO_TRACKING, SOUNDCLOUD_TRACKING,
  SHORT_LINK_DOMAINS } from './config.js';

const instagramContentPath=new RegExp(INSTAGRAM_CONTENT_PATH,'i');
const fixerHosts = new Set(Object.values(PROVIDERS).flatMap(p => Object.values(p.options)));
const extraTracking = new Map();
for (const [hosts, keys] of [[YOUTUBE_HOSTS,YOUTUBE_TRACKING],[AMAZON_TLDS,AMAZON_TRACKING],
  [EBAY_TLDS,EBAY_TRACKING],[ALIEXPRESS_DOMAINS,ALIEXPRESS_TRACKING],
  [['linkedin.com'],LINKEDIN_TRACKING],[PINTEREST_DOMAINS,PINTEREST_TRACKING],
  [['music.apple.com'],APPLE_MUSIC_TRACKING],[['vimeo.com'],VIMEO_TRACKING],
  [['soundcloud.com'],SOUNDCLOUD_TRACKING]]) {
  for (const host of hosts) extraTracking.set(host, keys);
}
export function trim(raw) {
  const url = raw.replace(/[.,!?);:\]>} ]+$/g, '');
  return [url, raw.slice(url.length)];
}
export function urls(text) { return [...text.matchAll(/https?:\/\/[^\s<>]+/gi)].map(m => trim(m[0])[0]); }
const hostOf = url => url.hostname.toLowerCase().replace(/^www\./, '');
export function platformFor(url) {
  const host = hostOf(url);
  if (fixerHosts.has(host)) return null;
  for (const [platform,p] of Object.entries(PROVIDERS)) {
    if (p.domains.some(d => host === d || host.endsWith('.'+d))) return platform;
  }
  return null;
}
export function stripTracking(raw, platform=null) {
  const url = new URL(raw);
  platform ??= Object.entries(PROVIDERS).find(([,p]) =>
    p.domains.some(d => hostOf(url)===d||hostOf(url).endsWith('.'+d)) || Object.values(p.options).includes(hostOf(url)))?.[0];
  const host=hostOf(url),config=PROVIDERS[platform];
  const hostKeys=[...extraTracking].filter(([domain])=>host===domain||host.endsWith('.'+domain)||
    config?.domains.some(d=>d===domain||d.endsWith('.'+domain))).flatMap(([,keys])=>keys);
  const drop = new Set([...GENERIC_TRACKING,...hostKeys,
    ...(platform?[...TRACKING,...(PLATFORM_TRACKING[platform]??[])]:[])].map(k=>k.toLowerCase()));
  // Public Instagram content only needs its path and optional carousel index.
  // Share-token names change; do not depend on a complete tracking denylist.
  const instagramContent=platform==='instagram'&&instagramContentPath.test(url.pathname);
  let changed = false;
  for (const key of [...url.searchParams.keys()]) if (drop.has(key.toLowerCase()) || /^utm_/i.test(key) ||
    (instagramContent&&!INSTAGRAM_CONTENT_QUERY.includes(key.toLowerCase()))) {
    url.searchParams.delete(key); changed = true;
  }
  return changed ? url.href : raw;
}
export function applyProvider(raw, platform, key) {
  const p = PROVIDERS[platform];
  if (!p?.options[key]) return raw;
  const u = new URL(raw); u.hostname = p.options[key]; u.port = ''; u.username = ''; u.password = '';
  return stripTracking(u.href, platform);
}
export function fixedFor(raw, platform, key) {
  const previewKey=PROVIDERS[platform]?.noauth_embed?.[key]??key;
  if(platform==='youtube'&&PROVIDERS.youtube.options[key]) {
    const official=new URL(raw);
    if(!YOUTUBE_HOSTS.includes(hostOf(official)))official.hostname='www.youtube.com';
    official.protocol='https:';official.port='';official.username='';official.password='';
    const url=stripTracking(official.href,'youtube');
    return {url,preview:key==='native'?url:applyProvider(url,platform,key)};
  }
  if(platform==='instagram'&&PROVIDERS.instagram.options[key]) {
    const official=new URL(raw);
    official.protocol='https:';official.hostname='instagram.com';official.port='';official.username='';official.password='';
    const url=stripTracking(official.href,'instagram');
    return {url,preview:applyProvider(url,platform,previewKey)};
  }
  const config=PROVIDERS[platform];
  if(!config?.options[key])return {url:raw,preview:raw};
  // Preserve deliberately selected no-account browser frontends.
  if(Object.hasOwn(config.noauth_embed??{},key))
    return {url:applyProvider(raw,platform,key),preview:applyProvider(raw,platform,previewKey)};
  const official=new URL(raw),host=hostOf(official);
  if(!config.domains.some(d=>host===d||host.endsWith('.'+d)))official.hostname=config.domains[0];
  official.protocol='https:';official.port='';official.username='';official.password='';
  return {url:stripTracking(official.href,platform),preview:applyProvider(official.href,platform,previewKey)};
}
// Recognize pasted embed-proxy links, while leaving deliberate browser
// frontends (e.g. XCancel/Redlib) alone.
export const rewritePlatform=u=>platformFor(u)??Object.entries(PROVIDERS).find(([,p])=>
  Object.entries(p.options).some(([key,host])=>hostOf(u)===host&&!Object.hasOwn(p.noauth_embed??{},key)))?.[0]??null;
// Telegram can provide a URL entity whose visible text omits the scheme.
export function normalizeEntityUrl(raw) {
  if (/^[a-z0-9.-]+(?:[/?#]|$)/i.test(raw) && !/\s/.test(raw)) {
    let url;
    try { url = new URL('https://' + raw); } catch { return raw; }
    const host = hostOf(url);
    if (!url.username && !url.password && !url.port &&
        (rewritePlatform(url) || SHORT_LINK_DOMAINS.includes(host))) return 'https://' + raw;
  }
  return raw;
}

// The browser destination may be an explicitly chosen alternative frontend.
export function duplicateDestination(link) {
  const raw = trim(link.url)[0];
  const config = PROVIDERS[link.platform];
  const target = config?.noauth_embed?.[link.key] ? fixedFor(raw, link.platform, link.previewKey).url : raw;
  const url = new URL(target);
  if (config) {
    const host = hostOf(url);
    url.hostname = link.platform === 'twitter' && ['x.com', 'twitter.com'].includes(host) ? 'x.com' : host;
  }
  return url.href;
}

function canonical(raw) {
  const u = new URL(raw), h = hostOf(u);
  const match = ['youtu.be','koutu.be'].includes(h) ? /^\/([\w-]+)/.exec(u.pathname) :
    ['youtube.com','m.youtube.com','music.youtube.com'].includes(h) ? /^\/(?:shorts|live)\/([^/?#]+)/i.exec(u.pathname) : null;
  if (match) {
    const result = new URL('https://www.youtube.com/watch'); result.searchParams.set('v',match[1]);
    // Preserve functional playlist, index and playback parameters; the shared
    // cleaner removes analytics after canonicalization.
    for(const [key,value] of u.searchParams)if(key.toLowerCase()!=='v')result.searchParams.append(key,value);
    result.hash=u.hash;
    return result.href;
  }
  if (AMAZON_TLDS.includes(h)) {
    const asin = /\/(?:dp|gp\/product|gp\/aw\/d|gp\/offer-listing|exec\/obidos\/ASIN|o\/ASIN)\/([A-Z0-9]{10})/i.exec(u.pathname);
    if (asin) return `${u.origin}/dp/${asin[1].toUpperCase()}`;
  }
  return raw;
}
// Expand known share links only, following at most four redirects and never
// fetching arbitrary user-supplied hosts. Each hop has its own bounded deadline.
export async function expand(raw, net=fetch, cache=null) {
  const first = new URL(raw), h = hostOf(first);
  if (!SHORT_LINK_DOMAINS.includes(h) && !(
    (h==='instagram.com' && /^\/share\//i.test(first.pathname)) ||
    (h==='tiktok.com' && /^\/t\//i.test(first.pathname)) ||
    (h==='reddit.com' && /^\/r\/[^/]+\/s\//i.test(first.pathname)))) return raw;
  const cached=await cache?.get('expand',raw);
  if(typeof cached==='string')return cached;
  let current = raw;
  const finish=async value=>{if(value!==raw&&value.length<=8192)await cache?.put('expand',raw,value,300);return value;};
  for (let i=0;i<4;i++) {
    const u = new URL(current), host = hostOf(u);
    if (!(SHORT_LINK_DOMAINS.includes(host) || platformFor(u))) return current;
    try {
      const r = await net(current,{redirect:'manual',headers:{'User-Agent':'TelegramBot (like TwitterBot)'},signal:AbortSignal.timeout(2000)});
      await r.body?.cancel();
      if (r.status<300 || r.status>=400 || !r.headers.get('location')) return r.ok?finish(current):current;
      const next = new URL(r.headers.get('location'),current);
      if (!['https:','http:'].includes(next.protocol) || next.username || next.password) return raw;
      current = next.href;
      if (hostOf(next) !== host && !SHORT_LINK_DOMAINS.includes(hostOf(next))) return finish(current);
    } catch { return current; }
  }
  return current;
}
export async function fixLink(raw, settings={}, choices={}, overrides={}, net=fetch, clean=false, health={},cache=null) {
  const [trimmed,tail] = trim(raw);
  let input;
  try {input = new URL(trimmed);} catch {return {url:raw};}
  if (!['https:','http:'].includes(input.protocol) || input.username || input.password) return {url:raw};
  const originalPlatform = rewritePlatform(input);
  if (!clean && originalPlatform && (overrides[originalPlatform]??(originalPlatform==='weibo'?0:1))===0) return {url:raw};
  const expanded = canonical(await expand(canonical(trimmed),net,cache));
  const platform = rewritePlatform(new URL(expanded));
  if (clean) return {url:stripTracking(expanded,platform)+tail};
  if (!platform) return {url:stripTracking(expanded)+tail,preview:stripTracking(expanded),raw:trimmed};
  if ((overrides[platform]??(platform==='weibo'?0:1))===0) return {url:raw};
  if (platform==='instagram' && !instagramContentPath.test(new URL(expanded).pathname) && !/^\/(s|share)\//i.test(new URL(expanded).pathname)) return {url:stripTracking(expanded,platform)+tail,preview:stripTracking(expanded,platform),raw:trimmed};
  if(platform==='furtrack'&&!/^\/p\/\d+\/?$/.test(new URL(expanded).pathname))return {url:stripTracking(expanded,platform)+tail,preview:stripTracking(expanded,platform),raw:trimmed};
  const p = PROVIDERS[platform], preferred = p.options[choices[platform]]?choices[platform]:p.default;
  const preferredPreview=p.noauth_embed?.[preferred]??preferred;
  const previewKey=settings.provider_fallback===0?preferredPreview:pickHealthy(platform,preferredPreview,health[platform]);
  const preserveBrowser=Object.hasOwn(p.noauth_embed??{},preferred);
  const selected=preserveBrowser?preferred:previewKey;
  // Post immediately with the selected provider. HTTP 403/404 on a single post
  // is not proof of provider failure; the button lets users choose an alternative.
  const fixed = fixedFor(expanded,platform,selected);
  if(preserveBrowser&&previewKey!==preferredPreview)fixed.preview=applyProvider(expanded,platform,previewKey);
  return {...fixed,url:fixed.url+tail,platform,key:selected,previewKey,raw:trimmed};
}
export async function processText(text, settings, choices, overrides, net=fetch, clean=false, health={},cache=null) {
  const tokens = [...new Set(text.match(/https?:\/\/[^\s<>]+/gi)??[])];
  // Bound external calls below Workers Free's subrequest limit.
  if (tokens.length>8) return {text,links:[],tooMany:true};
  let requests=0;
  const boundedNet=(...args)=>{if(requests++>=16)throw new Error('Short-link expansion budget reached');return net(...args);};
  const results=[];
  // Four active expansions leave room below the six-connection Free runtime ceiling.
  for(let i=0;i<tokens.length;i+=4)results.push(...await Promise.all(tokens.slice(i,i+4).map(async raw=>({original:raw,...await fixLink(raw,settings,choices,overrides,boundedNet,clean,health,cache)}))));
  const changed = results.filter(r=>r.original!==r.url || r.platform==='youtube' || (r.platform&&r.preview&&r.preview!==trim(r.url)[0]));
  const replacements = new Map(changed.map(r=>[r.original,r.url]));
  return {text:text.replace(/https?:\/\/[^\s<>]+/gi,m=>replacements.get(m)??m),links:changed,allLinks:results};
}
export const escapeHTML = text => String(text??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function senderLabel(user, mode) {
  if (!user || mode==='none') return '';
  if (mode==='username') return user.username?'@'+user.username:'';
  if (mode==='full_name') return [user.first_name,user.last_name].filter(Boolean).join(' ')||user.username||'User';
  return user.first_name||user.username||'User';
}
