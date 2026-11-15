import {PROVIDERS} from './config.js';
export const DEFAULTS = Object.freeze({enabled:1,sender_mode:'first_name',dedup_window:60,
  rate_limit:5,rate_window:30,ignore_forwards:1,provider_fallback:1,caption_style:'reply',text_spam:0});
export const SETTING_BOUNDS = Object.freeze({dedup_window:[5,3600],rate_limit:[1,100],rate_window:[5,3600]});
export function validSetting(key,value) {
  if (['enabled','ignore_forwards','provider_fallback','text_spam'].includes(key)) return value===0 || value===1;
  if (SETTING_BOUNDS[key]) return Number.isInteger(value) && value>=SETTING_BOUNDS[key][0] && value<=SETTING_BOUNDS[key][1];
  if (key==='sender_mode') return ['first_name','username','full_name','none'].includes(value);
  return key==='caption_style' && value==='reply';
}
export class Store {
  constructor(db,cache=null) { this.db=db;this.cache=cache; }
  stmt(sql,...params) { return this.db.prepare(sql).bind(...params); }
  async isMuted(chat,user) {return !!await this.stmt('SELECT user_id FROM blocked_users WHERE chat_id=? AND user_id=?',chat,user).first();}
  async settings(chat,user=0,{includeHealth=true}={}) {
    const [settings,users,mappings,flags]=await this.db.batch([
      this.stmt('SELECT * FROM chat_settings WHERE chat_id=?',chat),
      this.stmt('SELECT key,value FROM user_settings WHERE chat_id=? AND user_id=?',chat,user),
      this.stmt("SELECT platform,provider,NULL AS enabled,'provider' AS kind FROM provider_settings WHERE chat_id=? UNION ALL SELECT platform,NULL,enabled,'override' FROM platform_overrides WHERE chat_id=?",chat,chat),
      this.stmt('SELECT EXISTS(SELECT 1 FROM optout_users WHERE chat_id=? AND user_id=?) AS optout,EXISTS(SELECT 1 FROM blocked_users WHERE chat_id=? AND user_id=?) AS muted',chat,user,chat,user),
    ]);
    const result={...DEFAULTS,...settings.results[0]};
    for(const row of users.results) {const value=['sender_mode','caption_style'].includes(row.key)?row.value:Number(row.value);if(validSetting(row.key,value))result[row.key]=value;}
    return {settings:result,choices:Object.fromEntries(mappings.results.filter(r=>r.kind==='provider'&&PROVIDERS[r.platform]?.options[r.provider]).map(r=>[r.platform,r.provider])),
      overrides:Object.fromEntries(mappings.results.filter(r=>r.kind==='override').map(r=>[r.platform,r.enabled])),
      optout:!!flags.results[0]?.optout,muted:!!flags.results[0]?.muted,health:includeHealth?await this.health():{}};
  }
  async setSetting(chat,key,value) {
    if (!validSetting(key,value)) throw new Error('Invalid setting');
    // Identifiers come only from the validated closed set above.
    await this.stmt(`INSERT INTO chat_settings(chat_id,${key}${key==='text_spam'?'':',text_spam'}) VALUES(?,?${key==='text_spam'?'':',0'}) ON CONFLICT(chat_id) DO UPDATE SET ${key}=excluded.${key}`,chat,value).run();
  }
  async choose(chat,platform,provider) {await this.stmt('INSERT OR REPLACE INTO provider_settings VALUES(?,?,?)',chat,platform,provider).run();}
  async override(chat,platform,enabled) {await this.stmt('INSERT OR REPLACE INTO platform_overrides VALUES(?,?,?)',chat,platform,enabled).run();}
  async opt(chat,user,value) {await this.stmt(value?'INSERT OR IGNORE INTO optout_users VALUES(?,?)':'DELETE FROM optout_users WHERE chat_id=? AND user_id=?',chat,user).run();}
  async mute(chat,user,value) {await this.stmt(value?'INSERT OR IGNORE INTO blocked_users VALUES(?,?)':'DELETE FROM blocked_users WHERE chat_id=? AND user_id=?',chat,user).run();}
  async claimUpdate(id,now) {
    const row=await this.stmt(`INSERT INTO deliveries VALUES(?,'processing',?) ON CONFLICT(update_id)
      DO UPDATE SET ts=excluded.ts WHERE deliveries.state='processing' AND deliveries.ts<? RETURNING update_id`,id,now,now-120).first();
    if (row) return 'claimed';
    const prior=await this.stmt('SELECT state FROM deliveries WHERE update_id=?',id).first();
    return prior?.state==='processing'?'busy':'duplicate';
  }
  async finishUpdate(id,state,now) {await this.stmt('UPDATE deliveries SET state=?,ts=? WHERE update_id=?',state,now,id).run();}
  async claimRecent(kind,chat,key,window,now) {
    const row=await this.stmt(`INSERT INTO recent_events VALUES(?,?,?,?) ON CONFLICT(kind,chat_id,event_key)
      DO UPDATE SET ts=excluded.ts WHERE recent_events.ts<=? RETURNING ts`,kind,chat,key,now,now-window).first();
    return !!row;
  }
  async releaseRecent(kind,chat,key,ts) {await this.stmt('DELETE FROM recent_events WHERE kind=? AND chat_id=? AND event_key=? AND ts=?',kind,chat,key,ts).run();}
  async rate(chat,user,event,limit,window,now) {
    const row=await this.stmt(`INSERT INTO rate_events SELECT ?,?,?,? WHERE
      (SELECT COUNT(*) FROM rate_events WHERE chat_id=? AND user_id=? AND ts>?) < ?
      ON CONFLICT DO NOTHING RETURNING event_id`,chat,user,event,now,chat,user,now-window,limit).first();
    return !!row;
  }
  async record(chat,id,raw,sender,platforms,user,now,details=null) {
    const stmts=[this.stmt('INSERT OR REPLACE INTO rewritten_messages VALUES(?,?,?,?,?)',chat,id,raw,sender,now)];
    if(details)stmts.push(this.stmt('INSERT OR REPLACE INTO message_originals VALUES(?,?,?,?,?,?)',chat,id,JSON.stringify(details.original),details.platform??null,details.provider??null,now));
    if(details?.post)stmts.push(this.stmt('INSERT INTO post_controls(chat_id,bot_msg_id,source_msg_id,user_id,state_json,ts) VALUES(?,?,?,?,?,?)',chat,id,details.source_id,user,JSON.stringify(details.post),now));
    for (const p of platforms) stmts.push(this.stmt(`INSERT INTO chat_stats VALUES(?,?,?,1,?)
      ON CONFLICT(chat_id,platform,sender_id) DO UPDATE SET count=count+1,last_ts=excluded.last_ts`,chat,p,user,now));
    await this.db.batch(stmts);
  }
  async rewrite(chat,id) {return this.stmt('SELECT * FROM rewritten_messages WHERE chat_id=? AND bot_msg_id=?',chat,id).first();}
  async original(chat,id) {return this.stmt('SELECT * FROM message_originals WHERE chat_id=? AND bot_msg_id=?',chat,id).first();}
  async updateProvider(chat,id,provider) {await this.stmt('UPDATE message_originals SET provider=? WHERE chat_id=? AND bot_msg_id=?',provider,chat,id).run();}
  async post(chat,id) {return this.stmt('SELECT * FROM post_controls WHERE chat_id=? AND bot_msg_id=? AND ts>?',chat,id,Math.floor(Date.now()/1000)-7*86400).first();}
  async sourcePost(chat,id) {return this.stmt('SELECT * FROM post_controls WHERE chat_id=? AND source_msg_id=? AND ts>?',chat,id,Math.floor(Date.now()/1000)-7*86400).first();}
  async savePost(chat,id,source,user,post,ts) {await this.stmt(`INSERT INTO post_controls(chat_id,bot_msg_id,source_msg_id,user_id,state_json,ts) VALUES(?,?,?,?,?,?) ON CONFLICT(chat_id,bot_msg_id) DO UPDATE SET state_json=excluded.state_json,ts=excluded.ts`,chat,id,source,user,JSON.stringify(post),ts).run();}
  async lockPost(chat,id,now) {return !!await this.stmt('UPDATE post_controls SET lock_until=? WHERE chat_id=? AND bot_msg_id=? AND lock_until<=? RETURNING bot_msg_id',now+60,chat,id,now).first();}
  async unlockPost(chat,id) {await this.stmt('UPDATE post_controls SET lock_until=0 WHERE chat_id=? AND bot_msg_id=?',chat,id).run();}
  async refreshOriginal(chat,id,post) {const first=post.links[post.preview_index??0];await this.db.batch([
    this.stmt('UPDATE message_originals SET original_json=?,platform=?,provider=? WHERE chat_id=? AND bot_msg_id=?',JSON.stringify(post.original),first?.platform??null,first?.previewKey??null,chat,id),
    this.stmt('UPDATE rewritten_messages SET original_url=?,sender_name=? WHERE chat_id=? AND bot_msg_id=?',first?.raw??first?.original??'',post.label,chat,id),
  ]);}
  async health() {const cached=await this.cache?.get('health','all');if(cached)return cached;const rows=(await this.stmt('SELECT * FROM provider_health').all()).results;const health=Object.fromEntries(Object.keys(PROVIDERS).map(p=>[p,Object.fromEntries(rows.filter(r=>r.platform===p).map(r=>[r.provider,r]))]));await this.cache?.put('health','all',health,30,65536);return health;}
  async recordLegacyAction(chat,id,provider) {await this.db.batch([
    this.stmt('UPDATE message_originals SET provider=? WHERE chat_id=? AND bot_msg_id=?',provider,chat,id),
    this.stmt('INSERT OR REPLACE INTO post_activity VALUES(?,?,?)',chat,id,Date.now()),
  ]);}
  async operation(id) {return this.stmt('SELECT * FROM post_operations WHERE operation_id=?',id).first();}
  async pendingOperation(chat,id) {return this.stmt("SELECT * FROM post_operations WHERE chat_id=? AND bot_msg_id=? AND state='pending' ORDER BY ts LIMIT 1",chat,id).first();}
  async prepareOperation(id,chat,msg,post,kind) {await this.stmt("INSERT OR IGNORE INTO post_operations SELECT ?,chat_id,bot_msg_id,?,?,'pending',ts FROM post_controls WHERE chat_id=? AND bot_msg_id=?",id,JSON.stringify(post),kind,chat,msg).run();return this.operation(id);}
  async failOperation(id) {await this.stmt("UPDATE post_operations SET state='failed' WHERE operation_id=?",id).run();}
  async tapAllowed(chat,id,now=Date.now()) {const r=await this.stmt('SELECT last_action_at FROM post_activity WHERE chat_id=? AND bot_msg_id=?',chat,id).first();return !r||now-r.last_action_at>=1000;}
  async commitOperation(op) {
    const post=JSON.parse(op.desired_json),first=post.links[post.preview_index??0];
    await this.db.batch([
      this.stmt('UPDATE post_controls SET state_json=? WHERE chat_id=? AND bot_msg_id=?',op.desired_json,op.chat_id,op.bot_msg_id),
      this.stmt('UPDATE message_originals SET original_json=?,platform=?,provider=? WHERE chat_id=? AND bot_msg_id=?',JSON.stringify(post.original),first?.platform??null,first?.previewKey??null,op.chat_id,op.bot_msg_id),
      this.stmt('UPDATE rewritten_messages SET original_url=?,sender_name=? WHERE chat_id=? AND bot_msg_id=?',first?.raw??first?.original??'',post.label,op.chat_id,op.bot_msg_id),
      this.stmt("UPDATE post_operations SET state='done',desired_json=? WHERE operation_id=?",JSON.stringify({links:[{previewKey:first?.previewKey??'original'}],preview_index:0}),op.operation_id),
      ...(op.kind==='callback'?[this.stmt('INSERT OR REPLACE INTO post_activity VALUES(?,?,?)',op.chat_id,op.bot_msg_id,Date.now())]:[]),
    ]);
  }
  async export(chat) {
    const names=['chat_settings','provider_settings','blocked_users','platform_overrides','optout_users','user_settings'];
    const data=await this.db.batch(names.map(n=>this.stmt(`SELECT * FROM ${n} WHERE chat_id=?`,chat)));
    return {version:1,chat_id:chat,settings:{...DEFAULTS,...data[0].results[0]},
      providers:Object.fromEntries(data[1].results.map(r=>[r.platform,r.provider])),
      muted_users:data[2].results.map(r=>r.user_id),
      platform_overrides:Object.fromEntries(data[3].results.map(r=>[r.platform,r.enabled])),
      optout_users:data[4].results.map(r=>r.user_id),user_settings:data[5].results};
  }
  async cleanup(now) {
    // Each delete is bounded; indexed retention predicates avoid large hourly write bursts.
    const expired=(table,condition,...params)=>this.stmt(`DELETE FROM ${table} WHERE rowid IN (SELECT rowid FROM ${table} WHERE ${condition} LIMIT 250)`,...params);
    await this.db.batch([
      expired('deliveries','ts<?',now-7*86400),
      expired('recent_events','ts<?',now-3600),
      expired('rate_events','ts<?',now-3600),
      expired('rewritten_messages','ts<?',now-7*86400),
      expired('message_originals','ts<?',now-7*86400),
      expired('post_controls','ts<?',now-7*86400),
      expired('post_operations','ts<?',now-7*86400),
      expired('post_activity','last_action_at<? OR NOT EXISTS(SELECT 1 FROM post_controls p WHERE p.chat_id=post_activity.chat_id AND p.bot_msg_id=post_activity.bot_msg_id)',(now-7*86400)*1000),
      expired('free_daily_usage','day<?',new Date((now-7*86400)*1000).toISOString().slice(0,10)),
    ]);

  }
}
