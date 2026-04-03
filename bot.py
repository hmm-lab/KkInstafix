import os
import re
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

INSTAGRAM_PATTERN = re.compile(
    r'https?://(?:www[.])?instagram[.]com\S*',
    re.IGNORECASE
)

TRACKING = [
    'igsh', 'igshid', 'utm_source', 'utm_medium',
    'utm_campaign', 'utm_content', 'utm_term',
    'utm_id', 'fbclid', 'ref', 'hl'
]

def clean_url(url):
    parsed = urlparse(url)
    netloc = parsed.netloc.replace('instagram.com', 'kkinstagram.com')
    params = parse_qs(parsed.query, keep_blank_values=True)
    kept = {}
    for k in params:
        if k.lower() not in TRACKING:
            kept[k] = params[k]
    query = urlencode(kept, doseq=True)
    return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, query, ''))

async def on_message(update, context):
    msg = update.message
    if not msg:
        return
    if not msg.text:
        return

    text = msg.text
    matches = INSTAGRAM_PATTERN.findall(text)
    if not matches:
        return

    new_text = text
    for url in matches:
        new_text = new_text.replace(url, clean_url(url))

    if new_text == text:
        return

    user = msg.from_user
    if user:
        name = user.full_name
        if user.username:
            name = name + ' (@' + user.username + ')'
    else:
        name = 'Someone'

    output = '[Instagram] ' + name + chr(10) + new_text

    try:
        await msg.delete()
        await context.bot.send_message(chat_id=msg.chat_id, text=output)
    except Exception:
        await msg.reply_text(text=output)

def main():
    app = Application.builder().token(TOKEN).build()
    handler = MessageHandler(filters.TEXT, on_message)
    app.add_handler(handler)
    app.run_polling()

if __name__ == '__main__':
    main()
