import json
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

TOKEN = os.environ.get("BOT_TOKEN")
SETTINGS_FILE = "provider_settings.json"
IMAGE_FILE = "30364.jpg"

# ── Providers ─────────────────────────────────────────────────────────────────

PROVIDERS = {
    "instagram": {
        "default": "kkinstagram",
        "domains": ["instagram.com"],
        "options": {
            "kk":   "kkinstagram.com",
            "dd":   "ddinstagram.com",
            "ee":   "eeinstagram.com",
            "ez":   "instagramez.com",
            "fxig": "fxig.seria.moe",
        },
    },
    "twitter": {
        "default": "vxtwitter",
        "domains": ["twitter.com"],
        "options": {
            "vx": "vxtwitter.com",
            "fx": "fxtwitter.com",
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
        "default": "vxtiktok",
        "domains": ["tiktok.com"],
        "options": {
            "vx":  "vxtiktok.com",
            "tnk": "tnktok.com",
            "tik": "tiktxk.com",
        },
    },
    "reddit": {
        "default": "rxddit",
        "domains": ["reddit.com"],
        "options": {
            "rx":  "rxddit.com",
            "rxy": "rxyddit.com",
        },
    },
    "threads": {
        "default": "fixthreads",
        "domains": ["threads.net"],
        "options": {
            "fix": "fixthreads.net",
        },
    },
    "bluesky": {
        "default": "bskx",
        "domains": ["bsky.app"],
        "options": {
            "bskx": "bskx.app",
            "vx":   "vxbsky.app",
            "fx":   "fxbsky.app",
        },
    },
    "pixiv": {
        "default": "phixiv",
        "domains": ["pixiv.net"],
        "options": {"ph": "phixiv.net"},
    },
    "tumblr": {
        "default": "tpmblr",
        "domains": ["tumblr.com"],
        "options": {"tp": "tpmblr.com"},
    },
}

TRACKING = [
    "igsh", "igshid", "utm_source", "utm_medium", "utm_campaign",
    "utm_content", "utm_term", "utm_id", "fbclid", "ref", "hl", "s", "si",
]

URL_RE    = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
SHORTS_RE = re.compile(r"^/shorts/([A-Za-z0-9_-]+)")
TAIL      = ".,!?)]}>\u201d\u2019"

FIXER_HOSTS = {
    host
    for plat in PROVIDERS.values()
    for host in plat["options"].values()
}

# Emoji per platform for inline buttons
PLATFORM_EMOJI = {
    "instagram": "📷",
    "twitter":   "🐦",
    "x":         "✖️",
    "tiktok":    "🎵",
    "reddit":    "🤖",
    "threads":   "🧵",
    "bluesky":   "🔵",
    "pixiv":     "🎨",
    "tumblr":    "📝",
}

# ── Settings ──────────────────────────────────────────────────────────────────

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
    if key in s and platform in s[key]:
        return s[key][platform]
    return PROVIDERS[platform]["default"]


def set_choice(s, cid, platform, provider):
    key = str(cid)
    s.setdefault(key, {})[platform] = provider
    dump(s)


def reset_all(s, cid):
    s[str(cid)] = {}
    dump(s)

# ── URL helpers ───────────────────────────────────────────────────────────────

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
    p = PROVIDERS[platform]
    host = p["options"][provider_key]
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
    return fixed, platform, url  # return original url too for callback

# ── Inline keyboard ───────────────────────────────────────────────────────────

def make_keyboard(platform, original_url):
    """One row of buttons, one per provider for this platform."""
    emoji = PLATFORM_EMOJI.get(platform, "🔗")
    options = PROVIDERS[platform]["options"]
    buttons = []
    for key in options:
        # callback_data: platform|provider_key|original_url
        # Telegram limits callback_data to 64 bytes so we encode minimally
        cb = f"{platform}|{key}|{original_url}"
        if len(cb.encode()) <= 64:
            buttons.append(InlineKeyboardButton(f"{emoji} {key}", callback_data=cb))
        else:
            # url too long — store hash, skip for now
            buttons.append(InlineKeyboardButton(f"{emoji} {key}", callback_data=f"{platform}|{key}|LONG"))
    # Split into rows of 4
    rows = [buttons[i:i+4] for i in range(0, len(buttons), 4)]
    return InlineKeyboardMarkup(rows)

# ── Handlers ──────────────────────────────────────────────────────────────────

SPECIAL_CMDS = ("/mehrab", "/mo", "/genius")


async def send_photo(context, cid):
    if not os.path.exists(IMAGE_FILE):
        await context.bot.send_message(chat_id=cid, text="Image not found.")
        return
    with open(IMAGE_FILE, "rb") as img:
        await context.bot.send_photo(chat_id=cid, photo=img)


def providers_text(settings, cid):
    rows = ["Providers for this chat:", ""]
    for plat in sorted(PROVIDERS):
        cur = get_choice(settings, cid, plat)
        opts = ", ".join(PROVIDERS[plat]["options"])
        rows += [f"{plat}: {cur}", f"options: {opts}", ""]
    rows += [
        "Commands:",
        "/setprovider instagram kk",
        "/resetproviders",
        "/providers",
        "/mehrab  /mo  /genius",
    ]
    return "\n".join(rows)


async def handle_message(update, context):
    msg = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    settings = load()
    cid = msg.chat_id

    # ── Commands ─────────────────────────────────────────────────────────────
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
                await msg.reply_text("Unknown platform.")
                return
            if prov not in PROVIDERS[plat]["options"]:
                await msg.reply_text("Unknown provider.")
                return
            set_choice(settings, cid, plat, prov)
            await msg.reply_text(f"Set {plat} → {prov}")
            return

        return

    # ── Link detection ────────────────────────────────────────────────────────
    urls = URL_RE.findall(text)
    if not urls:
        return

    new_text = text
    changed = False
    keyboard = None
    detected_platform = None
    orig_url = None

    for raw in urls:
        fixed, platform, original = fix_url(raw, settings, cid)
        if fixed != raw:
            new_text = new_text.replace(raw, fixed)
            changed = True
            if platform and not detected_platform:
                detected_platform = platform
                orig_url = original

    if not changed:
        return

    # Build inline keyboard for the first detected platform
    if detected_platform and orig_url:
        keyboard = make_keyboard(detected_platform, orig_url)

    sender = msg.from_user.first_name or "User"
    post_text = f"{sender}: {new_text}"

    try:
        await msg.delete()
        await context.bot.send_message(
            chat_id=cid,
            text=post_text,
            reply_markup=keyboard,
        )
    except Exception:
        await msg.reply_text(post_text, reply_markup=keyboard)


async def handle_callback(update, context):
    """Handle inline button taps — rewrite the message with chosen provider."""
    query = update.callback_query
    await query.answer()

    try:
        platform, provider_key, original_url = query.data.split("|", 2)
    except ValueError:
        return

    if original_url == "LONG" or platform not in PROVIDERS:
        await query.answer("Cannot convert — URL too long for callback.", show_alert=True)
        return

    if provider_key not in PROVIDERS[platform]["options"]:
        return

    fixed = apply_provider(original_url, platform, provider_key)

    # Reconstruct message text: keep everything except old URLs
    old_text = query.message.text or ""
    # Replace any existing fixed URL with the new one
    new_text = URL_RE.sub(lambda m: fixed if get_platform(urlparse(m.group()).netloc, urlparse(m.group()).path) else m.group(), old_text)

    try:
        await query.edit_message_text(
            text=new_text,
            reply_markup=make_keyboard(platform, original_url),
        )
    except Exception:
        pass


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()


if __name__ == "__main__":
    main()
