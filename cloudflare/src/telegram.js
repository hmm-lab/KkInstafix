export class TelegramError extends Error {
  constructor(code,description,retryAfter) {super(description);this.code=code;this.retryAfter=retryAfter;}
}
export class Telegram {
  constructor(token,net=(input,init)=>fetch(input,init)) {this.token=token;this.net=net;}
  async call(method,data={}) {
    let response;
    try {response=await this.net(`https://api.telegram.org/bot${this.token}/${method}`,{
      method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data),signal:AbortSignal.timeout(10000),
    });} catch {throw new TelegramError(0,'Telegram network request did not complete');}
    let body;
    try {body=await response.json();} catch {throw new TelegramError(response.status,'Invalid Telegram API response');}
    if (!body.ok) throw new TelegramError(body.error_code??response.status,body.description??'Telegram API error',body.parameters?.retry_after);
    return body.result;
  }
  async send(chat,text,options={}) {return this.call('sendMessage',{chat_id:chat,text,disable_notification:true,...options});}
  async deliver(chat,html,plain,options={}) {
    const attempts=[{text:html,parse_mode:'HTML',...options},
      {text:plain,...options,parse_mode:undefined,reply_markup:undefined},
      {text:plain,...options,parse_mode:undefined,reply_markup:undefined,link_preview_options:undefined},
      {text:plain,...options,parse_mode:undefined,reply_markup:undefined,link_preview_options:undefined,reply_parameters:undefined}];
    for (const attempt of attempts) {
      try {return await this.send(chat,attempt.text,attempt);}
      catch(error) {
        if (!(error instanceof TelegramError) || error.code!==400) throw error;
        console.warn(JSON.stringify({event:'telegram_bad_request',code:error.code}));
      }
    }
    throw new TelegramError(400,'Telegram rejected all rewritten message formats');
  }
  async remove(chat,id) {
    try {await this.call('deleteMessage',{chat_id:chat,message_id:id});return true;}
    catch(error) {console.warn(JSON.stringify({event:'delete_denied',code:error.code??0}));return false;}
  }
  async admin(chat,user,type) {
    if (type==='private') return true;
    if (!user) return false;
    try {const member=await this.call('getChatMember',{chat_id:chat,user_id:user});return ['creator','administrator'].includes(member.status);}
    catch {return false;}
  }
}
