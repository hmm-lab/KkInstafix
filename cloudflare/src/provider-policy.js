import {PROVIDERS} from './config.js';
export function quarantined(row,stamp=Math.floor(Date.now()/1000)) {
  return !!row&&row.cooldown_until>stamp&&row.checked_at>stamp-86400;
}
export function pickHealthy(platform,preferred,health={},stamp=Math.floor(Date.now()/1000)) {
  const cfg=PROVIDERS[platform];if(!cfg)return preferred;
  const effective=k=>cfg.noauth_embed?.[k]??k;
  if(!quarantined(health[effective(preferred)],stamp))return preferred;
  return Object.keys(cfg.options).find(k=>!Object.hasOwn(cfg.noauth_embed??{},k)&&!quarantined(health[k],stamp))??preferred;
}
export function nextHealthy(platform,index,health={},stamp=Math.floor(Date.now()/1000)) {
  const keys=Object.keys(PROVIDERS[platform]?.options??{});
  for(let n=0;n<keys.length;n++) {
    const key=keys[(index+n)%keys.length],effective=PROVIDERS[platform].noauth_embed?.[key]??key;
    if(!quarantined(health[effective],stamp))return key;
  }
  return keys[index%keys.length];
}
export function healthLabel(row,stamp=Math.floor(Date.now()/1000)) {
  if(quarantined(row,stamp))return 'temporarily skipped';
  if(!row)return 'not checked yet';
  if(row.evidence==='content_metadata'&&row.checked_at>stamp-86400)return 'public sample passed';
  return row.evidence.replaceAll('_',' ');
}
