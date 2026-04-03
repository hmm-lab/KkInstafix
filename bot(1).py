import os
import re
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from telegram.ext import Application, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN")

TRACKING = [
    'igsh', 'igshid', 'utm_source', 'utm_medium',
    'utm_campaign', 'utm_content', 'utm_term',
    'utm_id', 'fbclid', 'ref', 'hl', 's', 'si'
]

URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)

SHORTS_PATTERN = re.compile(
    r'https?://(?:www[.])?youtube[.]com/shorts/([A-Za-z0-9_-]+)',
    re.IGNORECASE
)

def strip_tracking(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    kept = {}
    for k in params:
        if k.lower() not in TRACKING:
            kept[k] = params[k]
    query = urlencode(kept, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, ''))

def fix_url(url):
    low = url.lower()

    shorts_match = SHORTS_PATTERN.match(url)
    if shorts_match:
        return 'https://www.youtube.com/watch?v=' + shorts_match.group(1)

    if 'instagram.com' in low:
        return strip_tracking(url.replace('instagram.com', 'kkinstagram.com'))

    if 'twitter.com' in low:
        return strip_tracking(url.replace('twitter.com', 'fxtwitter.com'))

    if '//x.com' in low or '//www.x.com' in low:
        fixed = re.sub(r'(?i)(https?://(?:www[.])?)(x[.]com)', r'\1fixupx.com', url)
        return strip_tracking(fixed)

    if 'tiktok.com' in low:
        return strip_tracking(url.replace('tiktok.com', 'vxtiktok.com'))

    if 'reddit.com' in low:
        return strip_tracking(url.replace('reddit.com', 'rxddit.com'))

    if 'bsky.app' in low:
        return url.replace('bsky.app', 'fxbsky.app')

    if 'pixiv.net' in low:
        return url.replace('pixiv.net', 'phixiv.net')

    if 'tumblr.com' in low:
        return url.replace('tumblr.com', 'tpmblr.com')

    return url

async def on_message(update, context):
    msg = update.message
    if not msg:
        return
    if not msg.text:
        return

    text = msg.text
    urls = URL_PATTERN.findall(text)
    if not urls:
        return

    new_text = text
    changed = False

    for url in urls:
        fixed = fix_url(url)
        if fixed != url:
            new_text = new_text.replace(url, fixed)
            changed = True

    if not changed:
        return

    user = msg.from_user
    if user:
        name = user.full_name
        if user.username:
            name = name + ' (@' + user.username + ')'
    else:
        name = 'Someone'

    output = name + ':' + chr(10) + new_text

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
