import {rewriteEntities,entityHTML,hasProtectedLinks} from './formatting.js';
import {trim,stripTracking,escapeHTML as h} from './links.js';

// Telegram entity offsets use UTF-16 units, just like JavaScript string slices.
export function messageLinks(text,entities=[]) {
  const links=entities.filter(e=>['url','text_link'].includes(e.type)&&
    Number.isInteger(e.offset)&&Number.isInteger(e.length)&&e.offset>=0&&e.length>0&&e.offset+e.length<=text.length)
    .map(e=>({...e,url:e.type==='text_link'?e.url:text.slice(e.offset,e.offset+e.length)}))
    .filter(e=>typeof e.url==='string');
  for(const match of text.matchAll(/https?:\/\/[^\s<>]+/gi)) {
    const [url]=trim(match[0]),offset=match.index;
    if(!links.some(e=>offset<e.offset+e.length&&offset+url.length>e.offset))
      links.push({type:'url',offset,length:url.length,url});
  }
  return links.sort((a,b)=>a.offset-b.offset);
}
export function messageSource(msg) {
  let text=msg.text??msg.caption??'';
  const entities=msg.text!==undefined?msg.entities:msg.caption_entities;
  // Keep link labels and their destinations in the plain fallback as well.
  for(const e of messageLinks(text,entities).filter(e=>e.type==='text_link').reverse()) {
    const label=text.slice(e.offset,e.offset+e.length);
    const suffix=text.slice(e.offset+e.length);
    const separator=suffix&&!/^\s/.test(suffix)?' ':'';
    text=text.slice(0,e.offset)+(label===e.url?label:`${label} (${e.url})`)+separator+suffix;
  }
  return text;
}
export function transformedMessage(text,entities=[],replacements=new Map()) {
  return rewriteEntities(text,entities,messageLinks(text,entities),replacements);
}
export function renderLinkedText(text,entities,replacements=new Map()) {
  const rich=transformedMessage(text,entities,replacements);
  return entityHTML(rich.text,rich.entities);
}
export function providerMatches(raw,config) {
  try {
    const u=new URL(raw),host=u.hostname.toLowerCase().replace(/^www\./,'');
    return ['https:','http:'].includes(u.protocol)&&!u.username&&!u.password&&
      (Object.values(config.options).includes(host)||config.domains.some(d=>host===d||host.endsWith('.'+d)));
  } catch {return false;}
}
export function linkIdentity(raw,platform,clean=true) {
  const original=trim(raw)[0];
  const u=new URL(clean?stripTracking(original,platform):original);
  return u.pathname+u.search+u.hash;
}

// One renderer for all providers, captions and multi-link posts.
export function formatRepost({text,entities=[],plainText,links,label}) {
  const first=links[0],url=trim(first.url)[0];
  const replacements=new Map(links.map(link=>[trim(link.original)[0],trim(link.url)[0]]));
  const protectedLinks=hasProtectedLinks(text,entities,messageLinks(text,entities));
  const attribution=label?(protectedLinks?`<i>Shared by ${h(label)}</i>`:`<i>Shared by <a href="${h(url)}">${h(label)}</a></i>`):'';
  const meaningful=entities.some(e=>['bold','italic','underline','strikethrough','spoiler','code','pre','blockquote','expandable_blockquote','custom_emoji'].includes(e.type));
  const bare=!meaningful&&links.length===1&&text.trim()===first.raw;
  const rich=bare?{text:label?'Shared by '+label:'Open link',entities:label?
    [{type:'italic',offset:0,length:10+label.length},{type:'text_link',offset:10,length:label.length,url}]:
    [{type:'text_link',offset:0,length:9,url}]}:transformedMessage(text,entities,replacements);
  if(!bare&&label) {
    const offset=rich.text.length+2;rich.text+='\n\nShared by '+label;
    rich.entities.push({type:'italic',offset,length:10+label.length});
    if(!protectedLinks)rich.entities.push({type:'text_link',offset:offset+10,length:label.length,url});
  }
  return {
    html:bare?(attribution||`<a href="${h(url)}">Open link</a>`):
      renderLinkedText(text,entities,replacements)+(attribution?'\n\n'+attribution:''),
    plain:bare?(label?`Shared by ${label}\n${plainText}`:plainText):plainText+(label?'\n\nShared by '+label:''),
    fallback:rich,protectedLinks,
  };
}
