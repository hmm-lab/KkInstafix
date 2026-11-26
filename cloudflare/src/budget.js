// Conservative bot allowances, intentionally below the account's Free quotas.
export const FREE_BUDGET=Object.freeze({queries:45,fetches:24,cacheCalls:16,dailyRequests:10000,rowsRead:2000000,rowsWritten:25000,maintenanceRead:3000000,maintenanceWrite:50000,storageBytes:200*1024*1024});
export class BudgetError extends Error {constructor(resource){super('Free-tier safety budget reached: '+resource);this.name='BudgetError';}}
export class InvocationBudget {
  constructor(limits=FREE_BUDGET){this.limits=limits;this.queries=1;this.workQueries=0;this.fetches=0;this.cacheCalls=0;this.rowsRead=0;this.rowsWritten=0;this.storageBytes=0;this.day=new Date().toISOString().slice(0,10);this.prior={};this.reservedWrites=0;}
  query(count=1){if(this.queries+count>this.limits.queries)throw new BudgetError('database statements');this.queries+=count;this.workQueries+=count;}
  observe(result){for(const r of Array.isArray(result)?result:[result]){const m=r?.meta??{};this.rowsRead+=m.rows_read??0;this.rowsWritten+=m.rows_written??0;if(m.size_after)this.storageBytes=m.size_after;}}
  cache(){if(this.cacheCalls>=this.limits.cacheCalls)return false;this.cacheCalls++;return true;}
  network(net){return (...args)=>{if(this.fetches>=this.limits.fetches)throw new BudgetError('outgoing requests');this.fetches++;return net(...args);};}
  async admit(db,maintenance=false){
    const r=await db.prepare('SELECT d.*,(SELECT storage_bytes FROM free_daily_usage ORDER BY day DESC LIMIT 1) AS last_storage FROM (SELECT 1) LEFT JOIN free_daily_usage d ON d.day=?').bind(this.day).first();this.prior=r?.day?r:{};this.storageBytes=r?.last_storage??0;
    const p=this.prior,l=this.limits;
    return (maintenance||(p.requests??0)<l.dailyRequests)&&(p.rows_read??0)<(maintenance?l.maintenanceRead:l.rowsRead)&&(p.rows_written??0)<(maintenance?l.maintenanceWrite:l.rowsWritten)&&(maintenance||this.storageBytes<l.storageBytes);
  }
  async reserveWrites(db,estimate,limit=this.limits.rowsWritten){
    const remaining=limit-this.rowsWritten;
    const previous=await db.prepare(`INSERT INTO free_daily_usage(day, rows_written)
      SELECT ?,? WHERE ?<=?
      ON CONFLICT(day) DO UPDATE SET rows_written=rows_written+excluded.rows_written
      WHERE rows_written+excluded.rows_written<=?
      RETURNING day`).bind(this.day,estimate,estimate,remaining,remaining).first();
    if(previous)this.reservedWrites+=estimate;
    return !!previous;
  }
  async persist(db){
    if(!this.workQueries&&!this.reservedWrites)return;
    // One admission read and the accounting write are included conservatively.
    await db.prepare(`INSERT INTO free_daily_usage VALUES(?,1,?,?,?) ON CONFLICT(day) DO UPDATE SET requests=requests+1,rows_read=rows_read+excluded.rows_read,rows_written=rows_written+excluded.rows_written,storage_bytes=CASE WHEN excluded.storage_bytes>0 THEN excluded.storage_bytes ELSE storage_bytes END`)
      .bind(this.day,this.rowsRead+4,this.rowsWritten+2+(this.reservedWrites?2:0)-this.reservedWrites,this.storageBytes).run();
  }
  snapshot(){return {paused:!!this.paused,day:this.day,usage:this.prior,soft_limits:this.limits,scope:'This bot; account-wide traffic and billing are separate'};}
}
class Statement {
  constructor(raw,budget){this.statement=raw;this.budget=budget;}
  bind(...args){return new Statement(this.statement.bind(...args),this.budget);}
  async all(){this.budget.query();const r=await this.statement.all();this.budget.observe(r);return r;}
  async run(){this.budget.query();const r=await this.statement.run();this.budget.observe(r);return r;}
  async first(column){const r=(await this.all()).results?.[0];return r===undefined?null:column===undefined?r:r[column];}
}
export class BudgetedDB {
  constructor(db,budget){this.db=db;this.budget=budget;}
  reserveWrites(estimate,limit){this.budget.query();return this.budget.reserveWrites(this.db,estimate,limit);}
  prepare(sql){return new Statement(this.db.prepare(sql),this.budget);}
  async batch(statements){this.budget.query(statements.length);const r=await this.db.batch(statements.map(s=>s.statement));this.budget.observe(r);return r;}
}
