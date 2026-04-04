import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN")
SETTINGS_FILE = "provider_settings.json"
IMAGE_FILE = "30364.jpg"

# ── Providers (reference: github.com/Kyrela/FixTweetBot) ─────────────────

PROVIDERS = {
    "instagram": {
        "default": "vx",
        "domains": ["instagram.com"],
        "options": {
            "vx":   "vxinstagram.com",
            "kk":   "kkinstagram.com",
            "dd":   "ddinstagram.com",
            "ee":   "eeinstagram.com",
            "ez":   "instagramez.com",
            "fxig": "fxig.seria.moe",
        },
    },
    "twitter": {
        "default": "vx",
        "domains": ["twitter.com"],
        "options": {
            "vx":  "vxtwitter.com",
            "fx":  "fxtwitter.com",
            "fix": "fixupx.com",
            "ez":  "twitterez.com",
        },
    },
    "x": {
        "default": "fixvx",
        "domains": ["x.com"],
        "options": {
            "fixvx":  "fixvx.com",
            "fixupx": "fixupx.com",
        },
    },
    "tiktok": {
        "default": "tnk",
        "domains": ["tiktok.com"],
        "options": {
            "tnk": "tnktok.com",
            "vx":  "vxtiktok.com",
            "tik": "tiktxk.com",
            "tfx": "tfxktok.com",
            "ez":  "tiktokez.com",
        },
    },
    "reddit": {
        "default": "vx",
        "domains": ["reddit.com"],
        "options": {
            "vx":  "vxreddit.com",
            "rx":  "rxddit.com",
            "rxy": "rxyddit.com",
            "ez":  "redditez.com",
        },
    },
    "facebook": {
        "default": "ez",
        "domains": ["facebook.com", "fb.com", "fb.watch"],
        "options": {
            "ez":  "facebookez.com",
            "fx":  "fxfb.seria.moe",
            "bed": "facebed.com",
        },
    },
    "threads": {
        "default": "fix",
        "domains": ["threads.net"],
        "options": {
            "fix": "fixthreads.net",
            "vx":  "vxthreads.net",
        },
    },
    "bluesky": {
        "default": "bskx",
        "domains": ["bsky.app"],
        "options": {
            "bskx":  "bskx.app",
            "bsyy":  "bsyy.app",
            "xbsky": "xbsky.app",
            "fx":    "fxbsky.app",
            "vx":    "vxbsky.app",
            "cbsky": "cbsky.app",
        },
    },
    "pixiv": {
        "default": "ph",
        "domains": ["pixiv.net"],
        "options": {"ph": "phixiv.net"},
    },
    "tumblr": {
        "default": "tp",
        "domains": ["tumblr.com"],
        "options": {
            "tp":  "tpmblr.com",
            "txt": "txtumblr.com",
        },
    },
    "bilibili": {
        "default": "vx",
        "domains": ["bilibili.com", "b23.tv"],
        "options": {
            "vx": "vxbilibili.com",
            "fx": "fxbilibili.seria.moe",
            "ez": "bilibliez.com",
        },
    },
    "snapchat": {
        "default": "ez",
        "domains": ["snapchat.com"],
        "options": {
            "ez": "snapchatez.com",
        },
    },
    "spotify": {
        "default": "fx",
        "domains": ["open.spotify.com"],
        "options": {
            "fx":  "fxspotify.com",
            "fix": "fixspotify.com",
        },
    },
    "twitch": {
        "default": "fx",
        "domains": ["twitch.tv", "clips.twitch.tv"],
        "options": {
            "fx": "fxtwitch.seria.moe",
        },
    },
    "ifunny": {
        "default": "ez",
        "domains": ["ifunny.co"],
        "options": {
            "ez": "ifunnyez.co",
        },
    },
    "furaffinity": {
        "default": "xfa",
        "domains": ["furaffinity.net"],
        "options": {
            "xfa": "xfuraffinity.net",
            "fxr": "fxraffinity.net",
        },
    },
    "deviantart": {
        "default": "fix",
        "domains": ["deviantart.com"],
        "options": {
            "fix": "fixdeviantart.com",
            "fx":  "fxdeviantart.com",
        },
    },
}

TRACKING = [
    "igsh", "igshid", "utm_source", "utm_medium", "utm_campaign",
    "utm_content", "utm_term", "utm_id", "fbclid", "ref", "hl", "s", "si",
]

URL_RE    = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
SHORTS_RE = re.compile(r"^/shorts/([A-Za-z0-9_-]+)")
TAIL      = ".,!?)]>}"

FIXER_HOSTS = {
    host
    for plat in PROVIDERS.values()
    for host in plat["options"].values()
}

PLATFORM_EMOJI = {
    "instagram":   "\U0001f4f7",
    "twitter":     "\U0001f426",
    "x":           "X",
    "tiktok":      "\U0001f3b5",
    "reddit":      "\U0001f916",
    "facebook":    "\U0001f4d8",
    "threads":     "\U0001f9f5",
    "bluesky":     "\U0001f535",
    "pixiv":       "\U0001f3a8",
    "tumblr":      "\U0001f4dd",
    "bilibili":    "\U0001f4fa",
    "snapchat":    "\U0001f47b",
    "spotify":     "\U0001f3a7",
    "twitch":      "\U0001f3ae",
    "ifunny":      "\U0001f602",
    "furaffinity": "\U0001f43e",
    "deviantart":  "\U0001f58c",
}


def load():
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def dump(s):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2)


def get_choice(s, cid, platform):
    key = str(cid)
    stored = s.get(key, {}).get(platform)
    if stored and stored in PROVIDERS[platform]["options"]:
        return stored
    return PROVIDERS[platform]["default"]


def set_choice(s, cid, platform, provider):
    key = str(cid)
    s.setdefault(key, {})[platform] = provider
    dump(s)


def reset_all(s, cid):
    s[str(cid)] = {}
    dump(s)


def strip_tracking(url):
    p = urlparse(url)
    kept = {k: v for k, v in parse_qs(p.query, keep_blank_values=True).items()
            if k.lower() not in TRACKING}
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(kept, doseq=True), ""))


def trim(raw):
    url, tail = raw, ""
    while url and url[-1] in TAIL:
        tail, url = url[-1] + tail, url[:-1]
    return url, tail


def get_platform(netloc, path):
    host = netloc.lower().removeprefix("www.")
    if host in FIXER_HOSTS:
        return None
    if host == "youtube.com" and SHORTS_RE.match(path):
        return "youtube_shorts"
    for plat, cfg in PROVIDERS.items():
        for dom in cfg["domains"]:
            if host == dom or host.endswith("." + dom):
                return plat
    return None


def apply_provider(url, platform, provider_key):
    host = PROVIDERS[platform]["options"][provider_key]
    parsed = urlparse(url)
    fixed = urlunparse((parsed.scheme, host, parsed.path, parsed.params, parsed.query, ""))
    return strip_tracking(fixed)


def fix_url(raw, settings, cid):
    url, tail = trim(raw)
    parsed = urlparse(url)
    platform = get_platform(parsed.netloc, parsed.path)
    if not platform:
        return raw, None, None
    if platform == "youtube_shorts":
        m = SHORTS_RE.match(parsed.path)
        if m:
            return "https://www.youtube.com/watch?v=" + m.group(1) + tail, None, None
        return raw, None, None
    provider = get_choice(settings, cid, platform)
    fixed = apply_provider(url, platform, provider) + tail
    return fixed, platform, url


def make_keyboard(platform, original_url):
    emoji = PLATFORM_EMOJI.get(platform, "?")
    options = PROVIDERS[platform]["options"]
    buttons = [
        InlineKeyboardButton(
            f"{emoji} {key}",
            callback_data=f"{platform}|{key}|{original_url}"
        )
        for key in options
        if len(f"{platform}|{key}|{original_url}".encode()) <= 64
    ]
    rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    return InlineKeyboardMarkup(rows) if rows else None


SPECIAL_CMDS = ("/mehrab", "/mo", "/genius")


async def send_photo(context, cid):
    if not os.path.exists(IMAGE_FILE):
        await context.bot.send_message(chat_id=cid, text="Image not found.")
        return
    with open(IMAGE_FILE, "rb") as img:
        await context.bot.send_photo(chat_id=cid, photo=img)


def providers_text(settings, cid):
    lines = ["Providers for this chat:", ""]
    for plat in sorted(PROVIDERS):
        cur = get_choice(settings, cid, plat)
        opts = ", ".join(PROVIDERS[plat]["options"])
        lines.append(f"{plat}: {cur}  (options: {opts})")
        lines.append("")
    lines += [
        "Commands:",
        "/setprovider instagram vx",
        "/resetproviders",
        "/providers",
        "/mehrab  /mo  /genius",
    ]
    return "\n".join(lines)


async def handle_message(update, context):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    settings = load()
    cid = msg.chat_id

    if text.startswith("/"):
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()

        if cmd in SPECIAL_CMDS:
            await send_photo(context, cid)
            return

        if cmd in ("/providers", "/help"):
            await msg.reply_text(providers_text(settings, cid))
            return

        if cmd == "/resetproviders":
            reset_all(settings, cid)
            await msg.reply_text("Reset to defaults.")
            return

        if cmd == "/setprovider":
            if len(parts) != 3:
                await msg.reply_text("Usage: /setprovider platform provider")
                return
            plat, prov = parts[1].lower(), parts[2].lower()
            if plat not in PROVIDERS:
                await msg.reply_text("Unknown platform. Try /providers")
                return
            if prov not in PROVIDERS[plat]["options"]:
                opts = ", ".join(PROVIDERS[plat]["options"])
                await msg.reply_text(f"Unknown provider. Options: {opts}")
                return
            set_choice(settings, cid, plat, prov)
            await msg.reply_text(f"Set {plat} to {prov}")
            return

        return

    urls = URL_RE.findall(text)
    if not urls:
        return

    new_text = text
    changed = False
    detected_platform = None
    orig_url = None
    first_fixed_url = None

    for raw in urls:
        fixed, platform, original = fix_url(raw, settings, cid)
        if fixed != raw:
            new_text = new_text.replace(raw, fixed)
            changed = True
            if platform and not detected_platform:
                detected_platform = platform
                orig_url = original
                first_fixed_url = fixed.split()[0]

    if not changed:
        return

    keyboard = (
        make_keyboard(detected_platform, orig_url)
        if detected_platform and orig_url
        else None
    )
    sender = msg.from_user.first_name or "User"
    post_text = f"{sender}: {new_text}"

    # Pin the preview to the fixed URL and force large media
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_fixed_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    try:
        await msg.delete()
        await context.bot.send_message(
            chat_id=cid,
            text=post_text,
            reply_markup=keyboard,
            link_preview_options=preview,
        )
    except Exception:
        await msg.reply_text(
            post_text,
            reply_markup=keyboard,
            link_preview_options=preview,
        )


async def handle_callback(update, context):
    query = update.callback_query
    await query.answer()

    try:
        platform, provider_key, original_url = query.data.split("|", 2)
    except ValueError:
        return

    if platform not in PROVIDERS or provider_key not in PROVIDERS[platform]["options"]:
        return

    fixed = apply_provider(original_url, platform, provider_key)
    old_text = query.message.text or ""

    def replace_url(m):
        p = urlparse(m.group())
        return fixed if get_platform(p.netloc, p.path) else m.group()

    new_text = URL_RE.sub(replace_url, old_text)

    preview = LinkPreviewOptions(
        is_disabled=False,
        url=fixed,
        prefer_large_media=True,
        show_above_text=False,
    )

    try:
        await query.edit_message_text(
            text=new_text,
            reply_markup=make_keyboard(platform, original_url),
            link_preview_options=preview,
        )
    except Exception:
        pass


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()


if __name__ == "__main__":
    main()
