import {escapeHTML as h} from './links.js';
// Capability checks are observations; Telegram can still reject an individual post.
export async function permissionStatus(msg,tg) {
  const chat=msg.chat,lines=['<b>Bot capabilities</b>'];
  let me,member,info;
  try {me=await tg.call('getMe');}catch {return lines.concat('Could not check Telegram permissions. Try /status again shortly.').join('\n');}
  if(chat.type==='private')return lines.concat('Read messages: yes (private chat)','Send messages: yes (this reply)','Previews: supported; rendering depends on Telegram and the provider','Delete originals: allowed for incoming private messages, subject to Telegram limits').join('\n');
  const results=await Promise.allSettled([tg.call('getChatMember',{chat_id:chat.id,user_id:me.id}),tg.call('getChat',{chat_id:chat.id})]);
  member=results[0].status==='fulfilled'?results[0].value:null;
  info=results[1].status==='fulfilled'?results[1].value:null;
  if(!member?.status)return lines.concat('Permissions: unavailable. Check the bot’s membership and administrator permissions, then retry /status.').join('\n');
  const admin=['creator','administrator'].includes(member.status),absent=['left','kicked'].includes(member.status),restricted=member.status==='restricted';
  const channel=chat.type==='channel',permissions=restricted?member:info?.permissions;
  const send=absent?false:channel?(admin?member.can_post_messages!==false:false):admin?true:permissions?.can_send_messages;
  const previews=send===false?false:admin?true:permissions?.can_add_web_page_previews;
  const readable=absent?false:channel?true:admin||me.can_read_all_group_messages===true;
  const verdict=v=>v===undefined?'unknown':v?'yes':'no';
  lines.push(`Membership: ${h(member.status)}`,`Read all group messages: ${verdict(readable)}`,`Send messages: ${verdict(send)}`,`Add previews: ${verdict(previews)}`,`Delete originals: ${verdict(admin&&(member.status==='creator'||member.can_delete_messages===true))}`);
  if(!readable)lines.push('To receive ordinary group links: make the bot an administrator, or use @BotFather → /setprivacy → Disable and remove/re-add the bot.');
  if(send===false)lines.push(channel?'Grant the bot “Post messages” in channel administrator permissions.':'Allow “Send messages” for the bot in group permissions.');
  if(previews===false)lines.push('Allow “Embed links” / link previews for the bot in group permissions.');
  if(!(admin&&(member.status==='creator'||member.can_delete_messages===true)))lines.push('To remove replaced originals: grant administrator → “Delete messages”.');
  if(send===undefined||previews===undefined)lines.push('Some permissions could not be verified. Check Telegram’s group permissions.');
  lines.push('Preview playback still depends on Telegram and the selected provider.');
  return lines.join('\n');
}

export function budgetStatus(budget) {
  if(!budget)return '';
  const {usage:p,soft_limits:l,day,paused}=budget.snapshot(),remaining=(value,max)=>Math.max(0,max-(value??0)).toLocaleString('en-GB');
  const reset=new Date(Date.parse(day+'T00:00:00Z')+86400000).toISOString().replace('T',' ').replace('.000Z',' UTC');
  return `\n\n<b>Bot safety allowances${paused?' · paused':''}</b>\nRequests remaining: ${remaining(p.requests,l.dailyRequests)}\nDatabase rows read remaining: ${remaining(p.rows_read,l.rowsRead)}\nDatabase rows written remaining: ${remaining(p.rows_written,l.rowsWritten)}\nDaily reset: ${reset}\nStorage remaining: ${Math.floor(Math.max(0,l.storageBytes-budget.storageBytes)/1048576)} MiB (does not reset daily)\nThese are this bot’s conservative allowances, not account-wide Cloudflare usage.`;
}
