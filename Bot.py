import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from telegram.ext import Application, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN")
SETTINGS_FILE = "provider_settings.json"

PROVIDERS = {
    "instagram": {
        "default": "kkinstagram",
        "domains": ["instagram.com"],
        "options": {
            "kkinstagram": "kkinstagram.com",
            "ddinstagram": "ddinstagram.com",
            "eeinstagram": "eeinstagram.com",
            "instagramez": "instagramez.com"
        }
    },
    "twitter": {
        "default": "vxtwitter",
        "domains": ["twitter.com"],
        "options": {
            "vxtwitter": "vxtwitter.com",
            "fxtwitter": "fxtwitter.com",
            "twitterez": "twitterez.com"
        }
    },
    "x": {
        "default": "fixvx",
        "domains": ["x.com"],
        "options": {
            "fixvx": "fixvx.com",
            "fixupx": "fixupx.com"
        }
    },
    "tiktok": {
        "default": "vxtiktok",
        "domains": ["tiktok.com"],
        "options": {
            "vxtiktok": "vxtiktok.com",
            "tnktok": "tnktok.com",
            "tfxktok": "tfxktok.com",
            "tiktxk": "tiktxk.com",
            "tiktokez": "tiktokez.com"
        }
    },
    "reddit": {
        "default": "rxddit",
        "domains": ["reddit.com"],
        "options": {
            "rxddit": "rxddit.com",
            "rxyddit": "rxyddit.com",
            "redditez": "redditez.com"
        }
    },
    "threads": {
        "default": "fixthreads",
        "domains": ["threads.net"],
        "options": {
            "fixthreads": "fixthreads.net"
        }
    },
    "bluesky": {
        "default": "bskx",
        "domains": ["bsky.app"],
        "options": {
            "bskx": "bskx.app",
            "bsyy": "bsyy.app",
            "bskye": "bskye.app",
            "vxbsky": "vxbsky.app",
            "fxbsky": "fxbsky.app"
        }
    },
    "pixiv": {
        "default": "phixiv",
        "domains": ["pixiv.net"],
        "options": {
            "phixiv": "phixiv.net"
        }
    },
    "tumblr": {
        "default": "tpmblr",
        "domains": ["tumblr.com"],
        "options": {
            "tpmblr": "tpmblr.com"
        }
    }
}

TRACKING_PARAMS = [
    "igsh", "igshid", "utm_source", "utm_medium", "utm_campaign",
    "utm_content", "utm_term", "utm_id", "fbclid", "ref", "hl",
    "s", "si"
]

URL_RE = re.compile(r'https?://[^\s<>]+', re.IGNORECASE)
SHORTS_RE = re.compile(r'^/shorts/([A-Za-z0-9_-]+)')
TRAILING_PUNCT = '.,!?)]}>'

FIXER_HOSTS = set()
for _p in PROVIDERS:
    for _k in PROVIDERS[_p]["options"]:
        FIXER_HOSTS.add(PROVIDERS[_p]["options"][_k])


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        f = open(SETTINGS_FILE, 'r', encoding='utf-8')
        data = json.load(f)
        f.close()
        return data
    except Exception:
        return {}


def save_settings(settings):
    f = open(SETTINGS_FILE, 'w', encoding='utf-8')
    json.dump(settings, f, indent=2)
    f.close()


def get_choice(settings, chat_id, platform):
    k = str(chat_id)
    if k in settings and platform in settings[k]:
        return settings[k][platform]
    return PROVIDERS[platform]["default"]


def set_choice(settings, chat_id, platform, provider):
    k = str(chat_id)
    if k not in settings:
        settings[k] = {}
    settings[k][platform] = provider
    save_settings(settings)


def reset_choices(settings, chat_id):
    k = str(chat_id)
    if k in settings:
        settings[k] = {}
    save_settings(settings)


def strip_tracking(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    kept = {}
    for key in params:
        if key.lower() not in TRACKING_PARAMS:
            kept[key] = params[key]
    query = urlencode(kept, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, ''))


def trim_url(raw):
    url = raw
    tail = ''
    while len(url) > 0 and url[-1] in TRAILING_PUNCT:
        tail = url[-1] + tail
        url = url[:-1]
    return url, tail


def detect_platform(hostname, path):
    host = hostname.lower()
    if host.startswith('www.'):
        host = host[4:]
    if host in FIXER_HOSTS:
        return None
    if host == 'youtube.com':
        if SHORTS_RE.match(path):
            return 'youtube_shorts'
    for platform in PROVIDERS:
        for domain in PROVIDERS[platform]["domains"]:
            if host == domain or host.endswith('.' + domain):
                return platform
    return None


def rebuild_host(url, new_host):
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, new_host, parsed.path, parsed.params, parsed.query, ''))


def fix_url(raw, settings, chat_id):
    url, tail = trim_url(raw)
    parsed = urlparse(url)
    platform = detect_platform(parsed.netloc, parsed.path)
    if not platform:
        return raw
    if platform == 'youtube_shorts':
        m = SHORTS_RE.match(parsed.path)
        if not m:
            return raw
        return 'https://www.youtube.com/watch?v=' + m.group(1) + tail
    provider = get_choice(settings, chat_id, platform)
    new_host = PROVIDERS[platform]["options"][provider]
    fixed = rebuild_host(url, new_host)
    fixed = strip_tracking(fixed)
    return fixed + tail


def providers_text(settings, chat_id):
    lines = ['Current providers for this chat:', '']
    for platform in sorted(PROVIDERS.keys()):
        current = get_choice(settings, chat_id, platform)
        opts = ', '.join(sorted(PROVIDERS[platform]["options"].keys()))
        lines.append(platform + ': ' + current)
        lines.append('Options: ' + opts)
        lines.append('')
    lines.append('To change:')
    lines.append('/setprovider instagram ddinstagram')
    lines.append('/setprovider twitter fxtwitter')
    lines.append('/resetproviders')
    return '\n'.join(lines)


async def handle(update, context):
    msg = update.message
    if not msg or not msg.text:
        return
    text = msg.text.strip()
    settings = load_settings()
    chat_id = msg.chat_id

    if text.startswith('/'):
        parts = text.split()
        cmd = parts[0].split('@')[0].lower()

        if cmd in ('/help', '/providers'):
            await msg.reply_text(providers_text(settings, chat_id))
            return

        if cmd == '/resetproviders':
            reset_choices(settings, chat_id)
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
            set_choice(settings, chat_id, platform, provider)
            await msg.reply_text('Set ' + platform + ' to ' + provider)
            return

        return

    urls = URL_RE.findall(text)
    if not urls:
        return

    new_text = text
    changed = False
    for raw in urls:
        fixed = fix_url(raw, settings, chat_id)
        if fixed != raw:
            new_text = new_text.replace(raw, fixed)
            changed = True

    if not changed:
        return

    try:
        await msg.delete()
        await context.bot.send_message(chat_id=chat_id, text=new_text)
    except Exception:
        await msg.reply_text(new_text)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle))
    app.run_polling()


if __name__ == '__main__':
    main()
