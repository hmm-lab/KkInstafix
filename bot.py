import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from telegram.ext import Application, MessageHandler, filters

TOKEN = os.environ.get('BOT_TOKEN')
SETTINGS_FILE = 'provider_settings.json'

PROVIDERS = {
    'instagram': {'default': 'kkinstagram', 'domains': ['instagram.com'], 'options': {'kkinstagram': 'kkinstagram.com', 'ddinstagram': 'ddinstagram.com', 'eeinstagram': 'eeinstagram.com', 'instagramez': 'instagramez.com'}},
    'twitter':   {'default': 'vxtwitter',   'domains': ['twitter.com'],   'options': {'vxtwitter': 'vxtwitter.com', 'fxtwitter': 'fxtwitter.com', 'twitterez': 'twitterez.com'}},
    'x':         {'default': 'fixvx',       'domains': ['x.com'],         'options': {'fixvx': 'fixvx.com', 'fixupx': 'fixupx.com'}},
    'tiktok':    {'default': 'vxtiktok',    'domains': ['tiktok.com'],    'options': {'vxtiktok': 'vxtiktok.com', 'tnktok': 'tnktok.com', 'tfxktok': 'tfxktok.com', 'tiktxk': 'tiktxk.com', 'tiktokez': 'tiktokez.com'}},
    'reddit':    {'default': 'rxddit',      'domains': ['reddit.com'],    'options': {'rxddit': 'rxddit.com', 'rxyddit': 'rxyddit.com', 'redditez': 'redditez.com'}},
    'threads':   {'default': 'fixthreads',  'domains': ['threads.net'],   'options': {'fixthreads': 'fixthreads.net'}},
    'bluesky':   {'default': 'bskx',        'domains': ['bsky.app'],      'options': {'bskx': 'bskx.app', 'bsyy': 'bsyy.app', 'bskye': 'bskye.app', 'vxbsky': 'vxbsky.app', 'fxbsky': 'fxbsky.app'}},
    'pixiv':     {'default': 'phixiv',      'domains': ['pixiv.net'],     'options': {'phixiv': 'phixiv.net'}},
    'tumblr':    {'default': 'tpmblr',      'domains': ['tumblr.com'],    'options': {'tpmblr': 'tpmblr.com'}},
}

TRACKING = ['igsh','igshid','utm_source','utm_medium','utm_campaign','utm_content','utm_term','utm_id','fbclid','ref','hl','s','si']
URL_RE = re.compile(r'https?://[^\s<>]+', re.IGNORECASE)
SHORTS_RE = re.compile(r'^/shorts/([A-Za-z0-9_-]+)')
TAIL_CHARS = '.,!?)]}>'

FIXER_HOSTS = set()
for _p in PROVIDERS:
    for _k in PROVIDERS[_p]['options']:
        FIXER_HOSTS.add(PROVIDERS[_p]['options'][_k])


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_settings(s):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as fh:
        json.dump(s, fh, indent=2)


def get_choice(s, chat_id, platform):
    k = str(chat_id)
    if k in s and platform in s[k]:
        return s[k][platform]
    return PROVIDERS[platform]['default']


def set_choice(s, chat_id, platform, provider):
    k = str(chat_id)
    if k not in s:
        s[k] = {}
    s[k][platform] = provider
    save_settings(s)


def reset_all(s, chat_id):
    k = str(chat_id)
    if k in s:
        s[k] = {}
    save_settings(s)


def strip_tracking(url):
    p = urlparse(url)
    params = parse_qs(p.query, keep_blank_values=True)
    kept = {k: v for k, v in params.items() if k.lower() not in TRACKING}
    q = urlencode(kept, doseq=True)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, q, ''))


def trim(raw):
    url = raw
    tail = ''
    while url and url[-1] in TAIL_CHARS:
        tail = url[-1] + tail
        url = url[:-1]
    return url, tail


def get_platform(netloc, path):
    host = netloc.lower()
    if host.startswith('www.'):
        host = host[4:]
    if host in FIXER_HOSTS:
        return None
    if host == 'youtube.com' and SHORTS_RE.match(path):
        return 'youtube_shorts'
    for platform in PROVIDERS:
        for domain in PROVIDERS[platform]['domains']:
            if host == domain or host.endswith('.' + domain):
                return platform
    return None


def fix_url(raw, s, chat_id):
    url, tail = trim(raw)
    p = urlparse(url)
    platform = get_platform(p.netloc, p.path)
    if not platform:
        return raw
    if platform == 'youtube_shorts':
        m = SHORTS_RE.match(p.path)
        return 'https://www.youtube.com/watch?v=' + m.group(1) + tail if m else raw
    new_host = PROVIDERS[platform]['options'][get_choice(s, chat_id, platform)]
    fixed = urlunparse((p.scheme, new_host, p.path, p.params, p.query, ''))
    return strip_tracking(fixed) + tail


def providers_msg(s, chat_id):
    rows = ['Providers for this chat:', '']
    for pl in sorted(PROVIDERS):
        cur = get_choice(s, chat_id, pl)
        opts = ', '.join(sorted(PROVIDERS[pl]['options']))
        rows.append(pl + ': ' + cur)
        rows.append('options: ' + opts)
        rows.append('')
    rows.append('/setprovider instagram ddinstagram')
    rows.append('/resetproviders')
    return chr(10).join(rows)


async def handle(update, context):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    s = load_settings()
    cid = msg.chat_id

    if text.startswith('/'):
        parts = text.split()
        cmd = parts[0].split('@')[0].lower()
        if cmd in ('/help', '/providers'):
            await msg.reply_text(providers_msg(s, cid))
            return
        if cmd == '/resetproviders':
            reset_all(s, cid)
            await msg.reply_text('Providers reset to defaults.')
            return
               if cmd == '/dumbass':
            with open('30364.jpg', 'rb') as img:
                await context.bot.send_photo(chat_id=cid, photo=img)
            return
        
        if cmd == '/setprovider':
            if len(parts) != 3:
                await msg.reply_text('Usage: /setprovider platform provider')
                return
            pl = parts[1].lower()
            pv = parts[2].lower()
            if pl not in PROVIDERS:
                await msg.reply_text('Unknown platform. Try /providers')
                return
            if pv not in PROVIDERS[pl]['options']:
                await msg.reply_text('Unknown provider. Try /providers')
                return
            set_choice(s, cid, pl, pv)
            await msg.reply_text('Set ' + pl + ' to ' + pv)
            return
        return

    urls = URL_RE.findall(text)
    if not urls:
        return
    new_text = text
    changed = False
    for raw in urls:
        fixed = fix_url(raw, s, cid)
        if fixed != raw:
            new_text = new_text.replace(raw, fixed)
            changed = True
    if not changed:
        return
    try:
        await msg.delete()
        await context.bot.send_message(chat_id=cid, text=new_text)
    except Exception:
        await msg.reply_text(new_text)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle))
    app.run_polling()


if __name__ == '__main__':
    main()
