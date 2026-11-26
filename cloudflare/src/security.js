export async function readBounded(stream,limit=131072) {
  if (!stream) return new Uint8Array();
  const reader=stream.getReader(),chunks=[];let size=0;
  try {while(true) {const {value,done}=await reader.read();if(done)break;size+=value.length;
    if(size>limit){await reader.cancel();throw new Error('Payload too large');}chunks.push(value);}}
  finally {reader.releaseLock();}
  const bytes=new Uint8Array(size);let offset=0;
  for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
  return bytes;
}
export const hex=bytes=>[...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');
const unhex=s=>Uint8Array.from(s.match(/../g)??[],b=>parseInt(b,16));
export async function hash(s) {return hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(s)));}
export async function matchesSecret(provided,expectedHash) {
  const given=new TextEncoder().encode(await hash(provided??''));
  const expected=new TextEncoder().encode(expectedHash??'0'.repeat(64));
  return given.byteLength===expected.byteLength && crypto.subtle.timingSafeEqual(given,expected);
}
export async function seal(token,keyHex) {
  const key=await crypto.subtle.importKey('raw',unhex(keyHex),'AES-GCM',false,['encrypt']);
  const iv=crypto.getRandomValues(new Uint8Array(12));
  const encrypted=await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:new TextEncoder().encode('KkInstafix:bot-token:v1')},key,new TextEncoder().encode(token));
  return hex(iv)+':'+hex(encrypted);
}
export async function unseal(cipher,keyHex) {
  const [iv,data]=cipher.split(':');
  const key=await crypto.subtle.importKey('raw',unhex(keyHex),'AES-GCM',false,['decrypt']);
  const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:unhex(iv),additionalData:new TextEncoder().encode('KkInstafix:bot-token:v1')},key,unhex(data));
  return new TextDecoder().decode(plain);
}
