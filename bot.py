import json
import logging
import os
import re
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from telegram import LinkPreviewOptions
from telegram.ext import Application, MessageHandler, filters

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN        = os.environ.get("BOT_TOKEN")
SETTINGS_FILE = "provider_settings.json"
IMAGE_FILE   = "30364.jpg"

# ── Providers ──────────────────────────────────────────────────────────────────

PROVIDERS = {
    "instagram": {
        "default": "ee",
        "domains": ["instagram.com"],
        "options": {
            "ee":   "eeinstagram.com",
            "vx":   "vxinstagram.com",
            "kk":   "kkinstagram.com",
            "dd":   "ddinstagram.com",
            "ez":   "instagramez.com",
            "fxig": "fxig.seria.moe",
        },
    },
    # twitter.com and x.com are the same platform
    "twitter": {
        "default": "vx",
        "domains": ["twitter.com", "x.com"],
        "options": {
            "vx":     "vxtwitter.com",
            "fx":     "fxtwitter.com",
            "fixvx":  "fixvx.com",
            "fixupx": "fixupx.com",
            "ez":     "twitterez.com",
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
        "options": {"ez": "snapchatez.com"},
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
        "options": {"fx": "fxtwitch.seria.moe"},
    },
    "ifunny": {
        "default": "ez",
        "domains": ["ifunny.co"],
        "options": {"ez": "ifunnyez.co"},
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

SAMPLE_URLS = {
    "instagram": "https://www.instagram.com/p/C4example123/",
    "twitter":   "https://twitter.com/Twitter/status/1",
    "tiktok":    "https://www.tiktok.com/@tiktok/video/7106594312292453675",
    "reddit":    "https://www.reddit.com/r/funny/comments/1abc123/test/",
    "facebook":  "https://www.facebook.com/watch/?v=123456789",
    "threads":   "https://www.threads.net/@instagram/post/test",
    "bluesky":   "https://bsky.app/profile/bsky.app/post/test",
    "pixiv":     "https://www.pixiv.net/en/artworks/12345678",
    "tumblr":    "https://tumblr.com/blog/post/test",
    "bilibili":  "https://www.bilibili.com/video/BV1xx411c7mD",
    "spotify":   "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
    "twitch":    "https://clips.twitch.tv/test",
    "deviantart":"https://www.deviantart.com/test/art/test-12345",
}

# ── Deduplication & rate limiting ─────────────────────────────────────────────

DEDUP_WINDOW  = 60    # seconds — same link/media blocked within this window
RATE_LIMIT    = 5     # max link-fix actions per user per RATE_WINDOW seconds
RATE_WINDOW   = 30    # seconds for rate limit bucket

SEEN_UPDATES: set  = set()
RECENT_FIXES: dict = {}   # (chat_id, original_url) -> timestamp
RECENT_MEDIA: dict = {}   # (chat_id, file_unique_id) -> timestamp
USER_RATE:    dict = {}   # user_id -> [timestamps]


def _cleanup():
    cutoff = time.time() - max(DEDUP_WINDOW, RATE_WINDOW)
    for store in (RECENT_FIXES, RECENT_MEDIA):
        for k in [k for k, t in store.items() if t < cutoff]:
            del store[k]
    rate_cutoff = time.time() - RATE_WINDOW
    for uid in list(USER_RATE):
        USER_RATE[uid] = [t for t in USER_RATE[uid] if t >= rate_cutoff]
        if not USER_RATE[uid]:
            del USER_RATE[uid]


def is_duplicate_update(uid: int) -> bool:
    if uid in SEEN_UPDATES:
        return True
    SEEN_UPDATES.add(uid)
    if len(SEEN_UPDATES) > 2000:
        SEEN_UPDATES.clear()
    return False


def is_recent_fix(cid, url: str) -> bool:
    _cleanup()
    key = (cid, url)
    if key in RECENT_FIXES:
        return True
    RECENT_FIXES[key] = time.time()
    return False


def is_recent_media(cid, fuid: str) -> bool:
    _cleanup()
    key = (cid, fuid)
    if key in RECENT_MEDIA:
        return True
    RECENT_MEDIA[key] = time.time()
    return False


def check_rate(user_id: int) -> bool:
    """Returns True if user is within rate limit, False if throttled."""
    now = time.time()
    times = [t for t in USER_RATE.get(user_id, []) if now - t < RATE_WINDOW]
    if len(times) >= RATE_LIMIT:
        USER_RATE[user_id] = times
        return False
    times.append(now)
    USER_RATE[user_id] = times
    return True


# ── Settings ───────────────────────────────────────────────────────────────────

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
    stored = s.get(str(cid), {}).get(platform)
    if stored and stored in PROVIDERS[platform]["options"]:
        return stored
    return PROVIDERS[platform]["default"]


def set_choice(s, cid, platform, provider):
    s.setdefault(str(cid), {})[platform] = provider
    dump(s)


def reset_all(s, cid):
    s[str(cid)] = {}
    dump(s)


# ── URL helpers ────────────────────────────────────────────────────────────────

def strip_tracking(url):
    p = urlparse(url)
    kept = {k: v for k, v in parse_qs(p.query, keep_blank_values=True).items()
            if k.lower() not in TRACKING}
    return urlunparse((p.scheme, p.netloc, p.path, p.params,
                       urlencode(kept, doseq=True), ""))


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
    host   = PROVIDERS[platform]["options"][provider_key]
    parsed = urlparse(url)
    fixed  = urlunparse((parsed.scheme, host, parsed.path,
                         parsed.params, parsed.query, ""))
    return strip_tracking(fixed)


def fix_url(raw, settings, cid):
    url, tail = trim(raw)
    parsed    = urlparse(url)
    platform  = get_platform(parsed.netloc, parsed.path)
    if not platform:
        return raw, None, None
    if platform == "youtube_shorts":
        m = SHORTS_RE.match(parsed.path)
        if m:
            return ("https://www.youtube.com/watch?v=" + m.group(1) + tail,
                    None, None)
        return raw, None, None
    provider = get_choice(settings, cid, platform)
    fixed    = apply_provider(url, platform, provider) + tail
    return fixed, platform, url


def process_text(text, settings, cid):
    """Fix all URLs in text. Returns (new_text, changed, first_fixed_url)."""
    urls    = URL_RE.findall(text)
    new_text = text
    changed  = False
    first_fixed_url = None

    for raw in urls:
        fixed, platform, original = fix_url(raw, settings, cid)
        if fixed != raw:
            if original and is_recent_fix(cid, original):
                continue
            new_text = new_text.replace(raw, fixed)
            changed  = True
            if not first_fixed_url:
                first_fixed_url = fixed.split()[0]

    return new_text, changed, first_fixed_url


# ── Admin check ────────────────────────────────────────────────────────────────

async def is_admin(context, chat_id, user_id, chat_type):
    """Private chats always count as admin. Groups require admin status."""
    if chat_type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# ── Special commands ───────────────────────────────────────────────────────────

SPECIAL_CMDS = ("/mehrab", "/mo", "/genius")
ABOUT_CMDS   = ("/about", "/credits", "/me")

ABOUT_TEXT = (
    "\U0001f496 *About this bot*\n\n"
    "My name is Mehrab and I love you Motki \U0001f970\n\n"
    "This bot fixes social media links so they embed properly in Telegram. "
    "Send any Instagram, TikTok, Twitter/X, Reddit, Bluesky, Threads, Facebook, "
    "Spotify, Twitch or other link and I will convert it automatically.\n\n"
    "_Made with love by Mehrab_ \U0001f496"
)


async def send_photo(context, cid):
    if not os.path.exists(IMAGE_FILE):
        await context.bot.send_message(chat_id=cid, text="Image not found.")
        return
    with open(IMAGE_FILE, "rb") as img:
        await context.bot.send_photo(chat_id=cid, photo=img)


async def send_about(context, msg):
    if os.path.exists(IMAGE_FILE):
        with open(IMAGE_FILE, "rb") as img:
            await context.bot.send_photo(
                chat_id=msg.chat_id,
                photo=img,
                caption=ABOUT_TEXT,
                parse_mode="Markdown",
            )
    else:
        await msg.reply_text(ABOUT_TEXT, parse_mode="Markdown")


def providers_text(settings, cid):
    lines = ["Providers for this chat:", ""]
    for plat in sorted(PROVIDERS):
        cur  = get_choice(settings, cid, plat)
        opts = ", ".join(PROVIDERS[plat]["options"])
        lines.append(f"{plat}: {cur}  (options: {opts})")
        lines.append("")
    lines += [
        "Admin commands:",
        "/setprovider instagram vx",
        "/resetproviders",
        "/testall instagram",
        "/testall instagram https://instagram.com/p/ID/",
        "",
        "Commands:",
        "/providers",
        "/about  /credits  /me",
        "/mehrab  /mo  /genius",
    ]
    return "\n".join(lines)


async def handle_testall(msg, platform, custom_url=None):
    if platform not in PROVIDERS:
        await msg.reply_text(
            "Unknown platform. Available: " + ", ".join(sorted(PROVIDERS))
        )
        return
    base_url = custom_url or SAMPLE_URLS.get(platform)
    if not base_url:
        await msg.reply_text(
            "No sample URL. Pass one: /testall instagram https://..."
        )
        return
    options = PROVIDERS[platform]["options"]
    await msg.reply_text(
        f"Testing {len(options)} providers for {platform}...\n{base_url}"
    )
    for key, host in options.items():
        parsed = urlparse(base_url)
        fixed  = urlunparse((parsed.scheme, host, parsed.path,
                              parsed.params, parsed.query, ""))
        preview = LinkPreviewOptions(
            is_disabled=False, url=fixed,
            prefer_large_media=True, show_above_text=False,
        )
        try:
            await msg.reply_text(
                f"{PLATFORM_EMOJI.get(platform, chr(63))} [{key}] {fixed}",
                link_preview_options=preview,
            )
        except Exception as e:
            await msg.reply_text(f"[{key}] Error: {e}")


# ── Text message handler ───────────────────────────────────────────────────────

async def handle_message(update, context):
    msg = update.message
    if not msg or not msg.text:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if is_duplicate_update(update.update_id):
        return

    text     = msg.text.strip()
    settings = load()
    cid      = msg.chat_id
    uid      = msg.from_user.id if msg.from_user else 0

    if text.startswith("/"):
        parts = text.split()
        cmd   = parts[0].split("@")[0].lower()

        if cmd in SPECIAL_CMDS:
            await send_photo(context, cid)
            return

        if cmd in ABOUT_CMDS:
            await send_about(context, msg)
            return

        if cmd in ("/providers", "/help"):
            await msg.reply_text(providers_text(settings, cid))
            return

        # ── Admin-only commands below ──────────────────────────────────────
        admin = await is_admin(context, cid, uid, msg.chat.type)

        if cmd == "/resetproviders":
            if not admin:
                await msg.reply_text("Only admins can reset providers.")
                return
            reset_all(settings, cid)
            await msg.reply_text("Reset to defaults.")
            return

        if cmd == "/testall":
            if not admin:
                await msg.reply_text("Only admins can run testall.")
                return
            platform   = parts[1].lower() if len(parts) > 1 else "instagram"
            custom_url = parts[2] if len(parts) > 2 else None
            await handle_testall(msg, platform, custom_url)
            return

        if cmd == "/setprovider":
            if not admin:
                await msg.reply_text("Only admins can change providers.")
                return
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

    # Rate limit for link fixing
    if not check_rate(uid):
        logger.info("Rate limited user %s in chat %s", uid, cid)
        return

    new_text, changed, first_fixed_url = process_text(text, settings, cid)
    if not changed:
        return

    sender    = (msg.from_user.first_name or "User") if msg.from_user else "User"
    post_text = f"{sender}: {new_text}"
    preview   = LinkPreviewOptions(
        is_disabled=False, url=first_fixed_url,
        prefer_large_media=True, show_above_text=False,
    ) if first_fixed_url else None

    # Preserve reply chain
    reply_to = (
        msg.reply_to_message.message_id if msg.reply_to_message else None
    )

    logger.info("Fixed link in chat %s for user %s", cid, uid)

    try:
        await msg.delete()
        await context.bot.send_message(
            chat_id=cid,
            text=post_text,
            reply_to_message_id=reply_to,
            link_preview_options=preview,
        )
    except Exception:
        await msg.reply_text(post_text, link_preview_options=preview)


# ── Caption handler (photos/videos with links in caption) ─────────────────────

async def handle_caption(update, context):
    msg = update.message
    if not msg or not msg.caption:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if is_duplicate_update(update.update_id):
        return

    settings = load()
    cid = msg.chat_id
    uid = msg.from_user.id if msg.from_user else 0

    if not check_rate(uid):
        return

    new_cap, changed, first_fixed_url = process_text(
        msg.caption, settings, cid
    )
    if not changed:
        return

    preview = LinkPreviewOptions(
        is_disabled=False, url=first_fixed_url,
        prefer_large_media=True, show_above_text=False,
    ) if first_fixed_url else None

    sender = (msg.from_user.first_name or "User") if msg.from_user else "User"
    logger.info("Fixed caption link in chat %s for user %s", cid, uid)

    # Reply to the original media message with the fixed links
    await msg.reply_text(
        f"{sender} (fixed link): {new_cap}",
        link_preview_options=preview,
    )


# ── Media spam handler ────────────────────────────────────────────────────────

async def handle_media(update, context):
    msg = update.message
    if not msg:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if is_duplicate_update(update.update_id):
        return

    fuid = None
    if msg.sticker:
        fuid = msg.sticker.file_unique_id
    elif msg.animation:
        fuid = msg.animation.file_unique_id

    if not fuid:
        return

    if is_recent_media(msg.chat_id, fuid):
        logger.info("Deleted duplicate media in chat %s", msg.chat_id)
        try:
            await msg.delete()
        except Exception:
            pass


# ── Boot ──────────────────────────────────────────────────────────────────────

def validate_env():
    if not TOKEN:
        raise SystemExit(
            "ERROR: BOT_TOKEN environment variable is not set. "
            "Add it in your Railway service variables."
        )


async def on_startup(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started. Webhook cleared.")


def main():
    validate_env()
    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(on_startup)
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.VIDEO | filters.Document.ALL)
            & filters.CaptionRegex(r"https?://"),
            handle_caption,
        )
    )
    app.add_handler(MessageHandler(
        filters.Sticker.ALL | filters.ANIMATION, handle_media
    ))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
