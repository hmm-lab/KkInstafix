import {escapeHTML as h} from './links.js';

export function validEntities(text,entities=[]) {
  return entities.filter(e=>typeof e.type==='string'&&Number.isInteger(e.offset)&&Number.isInteger(e.length)&&
    e.offset>=0&&e.length>0&&e.offset+e.length<=text.length).map(e=>({...e}));
}
export function rewriteEntities(text,entities,links,replacements) {
  const original=validEntities(text,entities),edits=links.filter(e=>e.type==='url'&&replacements.has(e.url))
    .map(e=>({start:e.offset,end:e.offset+e.length,value:replacements.get(e.url)})).sort((a,b)=>a.start-b.start);
  let output='',last=0;
  for(const edit of edits){if(edit.start<last)continue;output+=text.slice(last,edit.start)+edit.value;last=edit.end;}
  output+=text.slice(last);
  const map=(pos,end=false)=>{
    let shift=0;
    for(const e of edits){if(pos>=e.end)shift+=e.value.length-(e.end-e.start);
      else if(pos>e.start)return e.start+shift+(end?e.value.length:0);else break;}
    return pos+shift;
  };
  const all=[...original];
  for(const link of links)if(!all.some(e=>e.type===link.type&&e.offset===link.offset&&e.length===link.length))all.push({...link});
  const mapped=all.map(e=>{
    const offset=map(e.offset),end=map(e.offset+e.length,true),next={...e,offset,length:end-offset};
    if(e.type==='text_link')next.url=replacements.get(e.url)??e.url;
    else delete next.url;
    return next;
  });
  const valid=validEntities(output,mapped);
  return {text:output,entities:valid.filter(e=>e.type!=='url'||!valid.some(c=>['code','pre'].includes(c.type)&&c.offset<=e.offset&&c.offset+c.length>=e.offset+e.length))};
}
function tags(e) {
  const simple={bold:['<b>','</b>'],italic:['<i>','</i>'],underline:['<u>','</u>'],strikethrough:['<s>','</s>'],
    spoiler:['<tg-spoiler>','</tg-spoiler>'],code:['<code>','</code>'],blockquote:['<blockquote>','</blockquote>'],
    expandable_blockquote:['<blockquote expandable>','</blockquote>']};
  if(simple[e.type])return simple[e.type];
  if(e.type==='pre')return e.language?[`<pre><code class="language-${h(e.language)}">`,'</code></pre>']:['<pre>','</pre>'];
  if(e.type==='text_link')return [`<a href="${h(e.url)}">`,'</a>'];
  if(e.type==='text_mention'&&Number.isSafeInteger(e.user?.id))return [`<a href="tg://user?id=${e.user.id}">`,'</a>'];
  if(e.type==='custom_emoji'&&/^\d+$/.test(e.custom_emoji_id??''))return [`<tg-emoji emoji-id="${e.custom_emoji_id}">`,'</tg-emoji>'];
  return null;
}
export function entityHTML(text,entities=[]) {
  const spans=validEntities(text,entities).map((e,i)=>({...e,i,tag:tags(e)})).filter(e=>e.tag);
  const points=[...new Set([0,text.length,...spans.flatMap(e=>[e.offset,e.offset+e.length])])].sort((a,b)=>a-b);
  let output='',stack=[];
  for(let i=0;i<points.length;i++) {
    const pos=points[i];let active=spans.filter(e=>e.offset<=pos&&e.offset+e.length>pos)
      .sort((a,b)=>a.offset-b.offset||(b.offset+b.length)-(a.offset+a.length)||a.i-b.i);
    // Telegram forbids inline formatting inside code/pre entities.
    if(active.some(e=>['code','pre'].includes(e.type)))active=active.filter(e=>['code','pre','blockquote','expandable_blockquote'].includes(e.type));
    let same=0;while(same<stack.length&&same<active.length&&stack[same].i===active[same].i)same++;
    for(let j=stack.length-1;j>=same;j--)output+=stack[j].tag[1];
    for(let j=same;j<active.length;j++)output+=active[j].tag[0];
    stack=active;
    if(i+1<points.length)output+=h(text.slice(pos,points[i+1]));
  }
  return output;
}
export const hasProtectedLinks=(text,entities,links)=>validEntities(text,entities).some(e=>e.type==='spoiler'&&
  links.some(l=>l.offset<e.offset+e.length&&l.offset+l.length>e.offset));

export function captureOriginal(msg) {
  const text=msg.text??msg.caption??'',isText=msg.text!==undefined;
  const snapshot={version:1,user_id:msg.from?.id??0,forwarded:!!msg.forward_origin,
    [isText?'text':'caption']:text,[isText?'entities':'caption_entities']:validEntities(text,isText?msg.entities:msg.caption_entities)};
  const photo=msg.photo?.at(-1)?.file_id;
  if(photo)snapshot.media={type:'photo',file_id:photo,has_spoiler:!!msg.has_media_spoiler,show_caption_above_media:!!msg.show_caption_above_media};
  else for(const type of ['video','animation','document','audio','voice'])if(msg[type]?.file_id){snapshot.media={type,file_id:msg[type].file_id,has_spoiler:!!msg.has_media_spoiler,show_caption_above_media:!!msg.show_caption_above_media};break;}
  return snapshot;
}
