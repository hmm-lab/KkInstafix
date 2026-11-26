import {PROVIDERS} from './config.js';
export function quarantined(row,stamp=Math.floor(Date.now()/1000)) {
  return !!row&&row.cooldown_until>stamp&&row.checked_at>stamp-86400;
}
export function eligibleAlternatives(platform,active,health={},after=active,stamp=Math.floor(Date.now()/1000)) {
  const config=PROVIDERS[platform];
  if(!config)return [];
  const keys=Object.keys(config.options),cursor=keys.indexOf(after);
  return [...keys.slice(cursor+1),...keys.slice(0,cursor+1)]
    .filter(key=>key!==active&&!Object.hasOwn(config.noauth_embed??{},key)&&!quarantined(health[key],stamp));
}
export function pickHealthy(platform,preferred,health={},stamp=Math.floor(Date.now()/1000)) {
  const backend=PROVIDERS[platform]?.noauth_embed?.[preferred]??preferred;
  if(!quarantined(health[backend],stamp))return backend;
  return eligibleAlternatives(platform,backend,health,null,stamp)[0]??'original';
}
export function healthLabel(row,stamp=Math.floor(Date.now()/1000)) {
  if(quarantined(row,stamp))return 'temporarily skipped';
  if(!row)return 'not checked yet';
  if(row.evidence==='content_metadata'&&row.checked_at>stamp-86400)return 'public sample passed';
  return row.evidence.replaceAll('_',' ');
}
