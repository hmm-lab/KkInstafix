import {hash} from './security.js';
import {VERSION} from './version.js';
// Cache API entries are local, expiring optimisations. D1 remains authoritative.
// User URLs are hashed in keys; no token, permission or user preference is cached.
export class JsonCache {
  constructor(cache,origin='https://kkinstafix.legend-mysterio.workers.dev',clock=()=>Date.now()) {this.cache=cache;this.origin=origin;this.clock=clock;}
  async key(namespace,key) {return new Request(`${this.origin}/_internal-cache/${VERSION}/${namespace}/${await hash(key)}`);}
  async get(namespace,key) {
    try {const r=await this.cache?.match(await this.key(namespace,key));if(!r)return null;const v=await r.json();return v.expires>this.clock()?v.value:null;}catch{return null;}
  }
  async put(namespace,key,value,ttl,maxBytes=8192) {
    try {const text=JSON.stringify({expires:this.clock()+ttl*1000,value});if(new TextEncoder().encode(text).length>maxBytes)return;
      await this.cache?.put(await this.key(namespace,key),new Response(text,{headers:{'Content-Type':'application/json','Cache-Control':`max-age=${ttl}`}}));
    }catch{/* Cache eviction or failure must never prevent delivery. */}
  }
  async remove(namespace,key) {try{await this.cache?.delete(await this.key(namespace,key));}catch{}}
}
