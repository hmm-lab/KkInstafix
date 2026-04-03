import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from telegram.ext import Application, MessageHandler, filters

TOKEN = os.environ.get('BOT_TOKEN')
SETTINGS_FILE = 'provider_settings.json'
IMAGE_dumbass = '30364.jpg'

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

TRACKING = ['igsh', 'igshid', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'utm_id', 'fbclid', 'ref', 'hl', 's', 'si']
URL_RE = re.compile(r'https?://[^\s<>]+', re.IGNORECASE)
SHORTS_RE = re.compile(r'^/shorts/([A-Za-z0-9_-]+)')
TAIL_CHARS = '.,!?)]}>'

FIXER_HOSTS = set()
for platform_name in PROVIDERS:
    for provider_name in PROVIDERS[platform_name]['options']:
        FIXER_HOSTS.add(PROVIDERS[platform_name]['options'][provider_name])


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_settings(settings):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as fh:
        json.dump(settings, fh, indent=2)


def get_choice(settings, chat_id, platform):
    key = str(chat_id)
    if key in settings and platform in settings[key]:
        return settings[key][platform]
    return PROVIDERS[platform]['default']


def set_choice(settings, chat_id, platform, provider):
    key = str(chat_id)
    if key not in settings:
        settings[key] = {}
    settings[key][platform] = provider
    save_settings(settings)


def reset_all(settings, chat_id):
    key = str(chat_id)
    if key in settings:
        settings[key] = {}
    save_settings(settings)


def strip_tracking(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    kept = {k: v for k, v in params.items() if k.lower() not in TRACKING}
    query = urlencode(kept, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, ''))


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


def fix_url(raw, settings, chat_id):
    url, tail = trim(raw)
    parsed = urlparse(url)
    platform = get_platform(parsed.netloc, parsed.path)
    if not platform:
        return raw
    if platform == 'youtube_shorts':
        match = SHORTS_RE.match(parsed.path)
        return 'https://www.youtube.com/watch?v=' + match.group(1) + tail if match else raw
    new_host = PROVIDERS[platform]['options'][get_choice(settings, chat_id, platform)]
    fixed = urlunparse((parsed.scheme, new_host, parsed.path, parsed.params, parsed.query, ''))
    return strip_tracking(fixed) + tail


def providers_msg(settings, chat_id):
    rows = ['Providers for this chat:', '']
    for platform in sorted(PROVIDERS):
        current = get_choice(settings, chat_id, platform)
        options = ', '.join(sorted(PROVIDERS[platform]['options']))
        rows.append(platform + ': ' + current)
        rows.append('options: ' + options)
        rows.append('')
    rows.append('/setprovider instagram ddinstagram')
    rows.append('/resetproviders')
    rows.append('/dumbass')
    return chr(10).join(rows)


async def send_dumbass_photo(context, chat_id):
    if not os.path.exists(IMAGE_dumbass):
        await context.bot.send_message(chat_id=chat_id, text='Missing 30364.jpg in the repo folder.')
        return
    with open(IMAGE_dumbass, 'rb') as img:
        await context.bot.send_photo(chat_id=chat_id, photo=img)


async def handle(update, context):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    settings = load_settings()
    cid = msg.chat_id

    if text.startswith('/'):
        parts = text.split()
        cmd = parts[0].split('@')[0].lower()

                if cmd in ('/mehrab', '/dumbass', '/pendejo'):
            await send_mehrab_photo(context, cid)
            return

        if cmd in ('/help', '/providers'):
            await msg.reply_text(providers_msg(settings, cid))
            return

        if cmd == '/resetproviders':
            reset_all(settings, cid)
            await msg.reply_text('Providers reset to defaults.')
            return

        if cmd == '/setprovider':
            if len(parts) != 3:
                await msg.reply_text('Usage: /setprovider platform provider')
                return
            platform = parts[1].lower()
            provider = parts[2].lower()
            if platform not in PROVIDERS:
                await msg.reply_text('Unknown platform. Try /providers')
                return
            if provider not in PROVIDERS[platform]['options']:
                await msg.reply_text('Unknown provider. Try /providers')
                return
            set_choice(settings, cid, platform, provider)
            await msg.reply_text('Set ' + platform + ' to ' + provider)
            return

        return

    urls = URL_RE.findall(text)
    if not urls:
        return

    new_text = text
    changed = False
    for raw in urls:
        fixed = fix_url(raw, settings, cid)
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
