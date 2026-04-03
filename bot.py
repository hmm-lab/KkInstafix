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

URL_RE = re.compile(r'https?://[^s<>]+', re.IGNORECASE)
SHORTS_RE = re.compile(r'^/shorts/([A-Za-z0-9_-]+)')
TRAILING_PUNCT = '.,!?)]}>'

FIXER_HOSTS = set()
for platform in PROVIDERS:
    for provider in PROVIDERS[platform]["options"]:
        FIXER_HOSTS.add(PROVIDERS[platform]["options"][provider])

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def get_choice(settings, chat_id, platform):
    chat_key = str(chat_id)
    if chat_key in settings and platform in settings[chat_key]:
        return settings[chat_key][platform]
    return PROVIDERS[platform]["default"]

def set_choice(settings, chat_id, platform, provider):
    chat_key = str(chat_id)
    if chat_key not in settings:
        settings[chat_key] = {}
    settings[chat_key][platform] = provider
    save_settings(settings)

def reset_choices(settings, chat_id):
    chat_key = str(chat_id)
    if chat_key in settings:
        settings[chat_key] = {}
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

def trim_url(raw_url):
    url = raw_url
    trailing = ''
    while len(url) > 0 and url[-1] in TRAILING_PUNCT:
        trailing = url[-1] + trailing
        url = url[:-1]
    return url, trailing

def detect_platform(hostname, path):
    host = hostname.lower()
    if host.startswith("www."):
        host = host[4:]

    if host in FIXER_HOSTS:
        return None

    if host == "youtube.com" or host == "www.youtube.com":
        if SHORTS_RE.match(path):
            return "youtube_shorts"

    for platform in PROVIDERS:
        for domain in PROVIDERS[platform]["domains"]:
            if host == domain or host.endswith("." + domain):
                return platform
    return None

def rebuild_with_host(url, new_host):
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, new_host, parsed.path, parsed.params, parsed.query, ''))

def fix_single_url(url, settings, chat_id):
    clean_url, trailing = trim_url(url)
    parsed = urlparse(clean_url)
    platform = detect_platform(parsed.netloc, parsed.path)

    if not platform:
        return url

    if platform == "youtube_shorts":
        match = SHORTS_RE.match(parsed.path)
        if not match:
            return url
        fixed = "https://www.youtube.com/watch?v=" + match.group(1)
        return fixed + trailing

    provider = get_choice(settings, chat_id, platform)
    new_host = PROVIDERS[platform]["options"][provider]
    fixed = rebuild_with_host(clean_url, new_host)
    fixed = strip_tracking(fixed)
    return fixed + trailing

def make_providers_text(settings, chat_id):
    lines = []
    lines.append("Current providers for this chat:")
    lines.append("")

    for platform in sorted(PROVIDERS.keys()):
        current = get_choice(settings, chat_id, platform)
        options = ", ".join(sorted(PROVIDERS[platform]["options"].keys()))
        lines.append(platform + ": " + current)
        lines.append("Options: " + options)
        lines.append("")

    lines.append("Commands:")
    lines.append("/providers")
    lines.append("/setprovider instagram ddinstagram")
    lines.append("/setprovider twitter fxtwitter")
    lines.append("/setprovider x fixupx")
    lines.append("/resetproviders")
    return "
".join(lines)

def normalize_command(token):
    return token.strip().split("@")[0].lower()

async def handle_text(update, context):
    message = update.message
    if not message or not message.text:
        return

    text = message.text.strip()
    settings = load_settings()
    chat_id = message.chat_id

    if text.startswith("/"):
        parts = text.split()
        command = normalize_command(parts[0])

        if command == "/providers" or command == "/help":
            await message.reply_text(make_providers_text(settings, chat_id))
            return

        if command == "/resetproviders":
            reset_choices(settings, chat_id)
            await message.reply_text("Provider choices reset to defaults for this chat.")
            return

        if command == "/setprovider":
            if len(parts) != 3:
                await message.reply_text("Usage: /setprovider <platform> <provider>")
                return

            platform = parts[1].lower()
            provider = parts[2].lower()

            if platform not in PROVIDERS:
                await message.reply_text("Unknown platform. Use /providers to see valid platforms.")
                return

            if provider not in PROVIDERS[platform]["options"]:
                await message.reply_text("Unknown provider for " + platform + ". Use /providers to see valid providers.")
                return

            set_choice(settings, chat_id, platform, provider)
            await message.reply_text("Set " + platform + " to " + provider + " for this chat.")
            return

        return

    urls = URL_RE.findall(text)
    if not urls:
        return

    new_text = text
    changed = False

    for raw_url in urls:
        fixed_url = fix_single_url(raw_url, settings, chat_id)
        if fixed_url != raw_url:
            new_text = new_text.replace(raw_url, fixed_url)
            changed = True

    if not changed:
        return

    try:
        await message.delete()
        await context.bot.send_message(chat_id=chat_id, text=new_text)
    except Exception:
        await message.reply_text(new_text)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_text))
    app.run_polling()

if __name__ == "__main__":
    main()
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
