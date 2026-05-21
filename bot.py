import asyncio
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from telegram import LinkPreviewOptions
from telegram.error import Conflict
from telegram.ext import Application, MessageHandler, filters

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
IMAGE_FILE = "30364.jpg"
DB_FILE = "bot_data.sqlite3"

# ── Providers ──────────────────────────────────────────────────────────────────
PROVIDERS = {
    "instagram": {
        "default": "kkclip",
        "domains": ["instagram.com"],
        "options": {
            "kkclip": "kkclip.com",
            "kk": "kkinstagram.com",
            "dd": "ddinstagram.com",
            "ez": "instagramez.com",
            "vx": "vxinstagram.com",
            "ee": "eeinstagram.com",
            "fxig": "fxig.seria.moe",
        },
    },
    "twitter": {
        "default": "vx",
        "domains": ["twitter.com", "x.com"],
        "options": {
            "vx": "vxtwitter.com",
            "fx": "fxtwitter.com",
            "fixvx": "fixvx.com",
            "fixupx": "fixupx.com",
            "ez": "twitterez.com",
        },
    },
    "tiktok": {
        "default": "tnk",
        "domains": ["tiktok.com"],
        "options": {
            "tnk": "tnktok.com",
            "vx": "vxtiktok.com",
            "tik": "tiktxk.com",
            "tfx": "tfxktok.com",
            "ez": "tiktokez.com",
        },
    },
    "reddit": {
        "default": "vx",
        "domains": ["reddit.com"],
        "options": {
            "vx": "vxreddit.com",
            "rx": "rxddit.com",
            "rxy": "rxyddit.com",
            "ez": "redditez.com",
        },
    },
    "facebook": {
        "default": "ez",
        "domains": ["facebook.com", "fb.com", "fb.watch"],
        "options": {
            "ez": "facebookez.com",
            "fx": "fxfb.seria.moe",
            "bed": "facebed.com",
        },
    },
    "threads": {
        "default": "fix",
        "domains": ["threads.net"],
        "options": {
            "fix": "fixthreads.net",
            "vx": "vxthreads.net",
        },
    },
    "bluesky": {
        "default": "bskx",
        "domains": ["bsky.app"],
        "options": {
            "bskx": "bskx.app",
            "bsyy": "bsyy.app",
            "xbsky": "xbsky.app",
            "fx": "fxbsky.app",
            "vx": "vxbsky.app",
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
            "tp": "tpmblr.com",
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
            "fx": "fxspotify.com",
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
            "fx": "fxdeviantart.com",
        },
    },
}

TRACKING = [
    "igsh", "igshid", "utm_source", "utm_medium", "utm_campaign",
    "utm_content", "utm_term", "utm_id", "fbclid", "ref", "hl", "s", "si",
]

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
SHORTS_RE = re.compile(r"^/shorts/([A-Za-z0-9_-]+)")
TAIL = ".,!?)]>}"
FIXER_HOSTS = {host for cfg in PROVIDERS.values() for host in cfg["options"].values()}
HEALTH_CACHE: dict = {}
HEALTH_TTL = 300
SEEN_UPDATES: OrderedDict = OrderedDict()
MAX_SEEN_UPDATES = 2000

DEFAULT_CHAT_SETTINGS = {
    "enabled": 1,
    "sender_mode": "first_name",
    "dedup_window": 60,
    "rate_limit": 5,
    "rate_window": 30,
    "ignore_forwards": 1,
    "provider_fallback": 1,
    "caption_style": "reply",
    "text_spam": 1,
}

PLATFORM_EMOJI = {
    "instagram": "📷",
    "twitter": "🐦",
    "tiktok": "🎵",
    "reddit": "🤖",
    "facebook": "📘",
    "threads": "🧵",
    "bluesky": "🔵",
    "pixiv": "🎨",
    "tumblr": "📝",
    "bilibili": "📺",
    "snapchat": "👻",
    "spotify": "🎧",
    "twitch": "🎮",
    "ifunny": "😂",
    "furaffinity": "🐾",
    "deviantart": "🖌",
}

SAMPLE_URLS = {
    "instagram": "https://www.instagram.com/p/C4example123/",
    "twitter": "https://twitter.com/Twitter/status/1",
    "tiktok": "https://www.tiktok.com/@tiktok/video/7106594312292453675",
    "reddit": "https://www.reddit.com/r/funny/comments/1abc123/test/",
    "facebook": "https://www.facebook.com/watch/?v=123456789",
    "threads": "https://www.threads.net/@instagram/post/test",
    "bluesky": "https://bsky.app/profile/bsky.app/post/test",
    "pixiv": "https://www.pixiv.net/en/artworks/12345678",
    "tumblr": "https://tumblr.com/blog/post/test",
    "bilibili": "https://www.bilibili.com/video/BV1xx411c7mD",
    "spotify": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
    "twitch": "https://clips.twitch.tv/test",
    "deviantart": "https://www.deviantart.com/test/art/test-12345",
}

ABOUT_TEXT = (
    "💖 *About this bot*\n\n"
    "My name is Mehrab and I love you Motki 🥰\n\n"
    "This bot fixes social media links so they embed properly in Telegram. "
    "It can also reduce repeated link, text, sticker, and GIF spam in groups.\n\n"
    "_Made with love by Mehrab_ 💖"
)

WELCOME_TEXT = (
    "Hi, I'm Mehrab's link fixer bot.\n\n"
    "I automatically rewrite supported social links so Telegram previews work better.\n"
    "Admins can use /status, /providers, /setprovider, /enable, /disable, /muteuser, and /testall.\n"
    "Try /about for credits."
)

# ── Database ───────────────────────────────────────────────────────────────────

_conn: sqlite3.Connection = None


def db_connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
    return _conn


def init_db():
    conn = db_connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS chat_settings (
            chat_id INTEGER PRIMARY KEY,
            enabled INTEGER NOT NULL DEFAULT 1,
            sender_mode TEXT NOT NULL DEFAULT 'first_name',
            dedup_window INTEGER NOT NULL DEFAULT 60,
            rate_limit INTEGER NOT NULL DEFAULT 5,
            rate_window INTEGER NOT NULL DEFAULT 30,
            ignore_forwards INTEGER NOT NULL DEFAULT 1,
            provider_fallback INTEGER NOT NULL DEFAULT 1,
            caption_style TEXT NOT NULL DEFAULT 'reply',
            text_spam INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS provider_settings (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            provider TEXT NOT NULL,
            PRIMARY KEY (chat_id, platform)
        );

        CREATE TABLE IF NOT EXISTS blocked_users (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS recent_events (
            kind TEXT NOT NULL,
            chat_id INTEGER NOT NULL,
            event_key TEXT NOT NULL,
            ts INTEGER NOT NULL,
            PRIMARY KEY (kind, chat_id, event_key)
        );

        CREATE TABLE IF NOT EXISTS rate_events (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            ts INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_rate_events_lookup
        ON rate_events(chat_id, user_id, ts);
        """
    )


def ensure_chat_settings(chat_id):
    conn = db_connect()
    cols = ", ".join(DEFAULT_CHAT_SETTINGS.keys())
    qs = ", ".join(["?"] * len(DEFAULT_CHAT_SETTINGS))
    conn.execute(
        f"INSERT OR IGNORE INTO chat_settings(chat_id, {cols}) VALUES (?, {qs})",
        [chat_id, *DEFAULT_CHAT_SETTINGS.values()],
    )
    conn.commit()


def get_chat_settings(chat_id):
    ensure_chat_settings(chat_id)
    conn = db_connect()
    row = conn.execute(
        "SELECT * FROM chat_settings WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    return dict(row) if row else DEFAULT_CHAT_SETTINGS.copy()


def update_chat_setting(chat_id, key, value):
    ensure_chat_settings(chat_id)
    conn = db_connect()
    conn.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()


def get_choice(chat_id, platform):
    ensure_chat_settings(chat_id)
    conn = db_connect()
    row = conn.execute(
        "SELECT provider FROM provider_settings WHERE chat_id = ? AND platform = ?",
        (chat_id, platform),
    ).fetchone()
    stored = row["provider"] if row else None
    if stored and stored in PROVIDERS[platform]["options"]:
        return stored
    return PROVIDERS[platform]["default"]


def set_choice(chat_id, platform, provider):
    conn = db_connect()
    conn.execute(
        "INSERT OR REPLACE INTO provider_settings(chat_id, platform, provider) VALUES(?, ?, ?)",
        (chat_id, platform, provider),
    )
    conn.commit()


def reset_providers(chat_id):
    conn = db_connect()
    conn.execute("DELETE FROM provider_settings WHERE chat_id = ?", (chat_id,))
    conn.commit()


def mute_user(chat_id, user_id):
    conn = db_connect()
    conn.execute(
        "INSERT OR IGNORE INTO blocked_users(chat_id, user_id) VALUES(?, ?)",
        (chat_id, user_id),
    )
    conn.commit()


def unmute_user(chat_id, user_id):
    conn = db_connect()
    conn.execute(
        "DELETE FROM blocked_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    conn.commit()


def is_user_muted(chat_id, user_id):
    conn = db_connect()
    row = conn.execute(
        "SELECT 1 FROM blocked_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    return bool(row)


def blocked_user_count(chat_id):
    conn = db_connect()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM blocked_users WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    return row["c"] if row else 0


def cleanup_db(max_age=86400):
    now = int(time.time())
    conn = db_connect()
    conn.execute("DELETE FROM recent_events WHERE ts < ?", (now - max_age,))
    conn.execute("DELETE FROM rate_events WHERE ts < ?", (now - max_age,))
    conn.commit()


def seen_recent(kind, chat_id, event_key, window):
    now = int(time.time())
    conn = db_connect()
    conn.execute(
        "DELETE FROM recent_events WHERE kind = ? AND ts < ?",
        (kind, now - window),
    )
    row = conn.execute(
        "SELECT 1 FROM recent_events WHERE kind = ? AND chat_id = ? AND event_key = ?",
        (kind, chat_id, event_key),
    ).fetchone()
    if row:
        return True
    conn.execute(
        "INSERT OR REPLACE INTO recent_events(kind, chat_id, event_key, ts) VALUES(?, ?, ?, ?)",
        (kind, chat_id, event_key, now),
    )
    conn.commit()
    return False


def check_rate(chat_id, user_id, limit_count, window):
    now = int(time.time())
    conn = db_connect()
    conn.execute(
        "DELETE FROM rate_events WHERE chat_id = ? AND user_id = ? AND ts < ?",
        (chat_id, user_id, now - window),
    )
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM rate_events WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    current = row["c"] if row else 0
    if current >= limit_count:
        return False
    conn.execute(
        "INSERT INTO rate_events(chat_id, user_id, ts) VALUES(?, ?, ?)",
        (chat_id, user_id, now),
    )
    conn.commit()
    return True

# ── Helpers ────────────────────────────────────────────────────────────────────

def is_duplicate_update(update_id):
    if update_id in SEEN_UPDATES:
        return True
    SEEN_UPDATES[update_id] = None
    if len(SEEN_UPDATES) > MAX_SEEN_UPDATES:
        SEEN_UPDATES.popitem(last=False)
    return False


def strip_tracking(url):
    parsed = urlparse(url)
    kept = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k.lower() not in TRACKING
    }
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(kept, doseq=True), "")
    )


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


def _check_url_sync(url: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=4):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


async def provider_alive(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    now = time.time()
    cached = HEALTH_CACHE.get(host)
    if cached and now - cached[1] < HEALTH_TTL:
        return cached[0]
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _check_url_sync, url)
    HEALTH_CACHE[host] = (result, now)
    return result


async def choose_provider_url(original_url, platform, preferred_key, allow_fallback=True):
    keys = list(PROVIDERS[platform]["options"].keys())
    ordered = [preferred_key] + [k for k in keys if k != preferred_key]
    chosen_url = apply_provider(original_url, platform, preferred_key)
    if not allow_fallback or len(ordered) == 1:
        return chosen_url, preferred_key
    for key in ordered:
        candidate = apply_provider(original_url, platform, key)
        if await provider_alive(candidate):
            return candidate, key
    return chosen_url, preferred_key


# Instagram paths that are actual posts/reels/stories - safe to convert
INSTAGRAM_CONTENT_RE = re.compile(
    r"^/(p|reel|tv|stories|s)/",
    re.IGNORECASE,
)


async def fix_url(raw, chat_id, chat_settings):
    url, tail = trim(raw)
    parsed = urlparse(url)
    platform = get_platform(parsed.netloc, parsed.path)
    if not platform:
        return raw, None, None
    if platform == "instagram" and not INSTAGRAM_CONTENT_RE.match(parsed.path):
        return raw, None, None
    if platform == "youtube_shorts":
        m = SHORTS_RE.match(parsed.path)
        if m:
            return "https://www.youtube.com/watch?v=" + m.group(1) + tail, None, None
        return raw, None, None
    preferred = get_choice(chat_id, platform)
    fixed, _ = await choose_provider_url(
        url,
        platform,
        preferred,
        allow_fallback=bool(chat_settings["provider_fallback"]),
    )
    return fixed + tail, platform, url


async def process_text(text, chat_id, chat_settings):
    urls = URL_RE.findall(text)
    new_text = text
    changed = False
    first_fixed_url = None
    dedup_window = int(chat_settings["dedup_window"])
    for raw in urls:
        fixed, platform, original = await fix_url(raw, chat_id, chat_settings)
        if fixed != raw:
            if original and seen_recent("fix", chat_id, original, dedup_window):
                continue
            new_text = new_text.replace(raw, fixed)
            changed = True
            if not first_fixed_url:
                first_fixed_url = fixed.split()[0]
    return new_text, changed, first_fixed_url


def _detected_platform(text):
    for plat, info in PROVIDERS.items():
        for domain in info["domains"]:
            if domain in text:
                return plat
    return None


def sender_label(user, mode):
    if not user or mode == "none":
        return None
    if mode == "username" and user.username:
        return "@" + user.username
    if mode == "full_name":
        full = " ".join(x for x in [user.first_name, user.last_name] if x)
        return full or user.first_name or "User"
    return user.first_name or user.username or "User"


def format_repost_text(user, text, mode, platform=None):
    label = sender_label(user, mode)
    if not label:
        return text
    emoji = PLATFORM_EMOJI.get(platform, "") + " " if platform else ""
    return f"{emoji}{label} shared: {text}"


def providers_text(chat_id):
    lines = ["Providers for this chat:", ""]
    for plat in sorted(PROVIDERS):
        cur = get_choice(chat_id, plat)
        opts = ", ".join(PROVIDERS[plat]["options"])
        lines.append(f"{plat}: {cur}  (options: {opts})")
        lines.append("")
    lines += [
        "Admin commands:",
        "/setprovider instagram vx",
        "/resetproviders",
        "/enable  /disable",
        "/muteuser (reply or user id)",
        "/unmuteuser (reply or user id)",
        "/setsendermode first_name|username|full_name|none",
        "/setdedup 60",
        "/setratelimit 5 30",
        "/ignoreforwards on|off",
        "/fallback on|off",
        "/textspam on|off",
        "/testall instagram",
        "",
        "Public commands:",
        "/providers  /status  /about  /credits  /me",
        "/mehrab  /mo  /genius",
    ]
    return "\n".join(lines)


def status_text(chat_id):
    s = get_chat_settings(chat_id)
    return "\n".join([
        "Chat status:",
        f"enabled: {bool(s['enabled'])}",
        f"sender_mode: {s['sender_mode']}",
        f"dedup_window: {s['dedup_window']}s",
        f"rate_limit: {s['rate_limit']} per {s['rate_window']}s",
        f"ignore_forwards: {bool(s['ignore_forwards'])}",
        f"provider_fallback: {bool(s['provider_fallback'])}",
        f"caption_style: {s['caption_style']}",
        f"text_spam: {bool(s['text_spam'])}",
        f"muted_users: {blocked_user_count(chat_id)}",
    ])


def parse_on_off(value):
    v = value.lower()
    if v in ("on", "true", "yes", "1"):
        return 1
    if v in ("off", "false", "no", "0"):
        return 0
    return None


def target_user_id_from_command(msg, parts):
    if msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user.id
    if len(parts) > 1 and parts[1].lstrip("-").isdigit():
        return int(parts[1])
    return None


def is_forwarded(msg):
    return bool(getattr(msg, "forward_origin", None) or getattr(msg, "forward_date", None))

# ── Permissions and messaging ──────────────────────────────────────────────────
async def is_admin(context, chat_id, user_id, chat_type):
    if chat_type == "private":
        return True
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Failed admin check in chat %s for user %s", chat_id, user_id)
        return False


async def safe_delete(msg, reason):
    try:
        await msg.delete()
        logger.info("Deleted message in chat %s (%s)", msg.chat_id, reason)
        return True
    except Exception:
        logger.exception("Delete failed in chat %s (%s)", msg.chat_id, reason)
        return False


async def safe_send_text(context, chat_id, text, preview=None, reply_to=None):
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            link_preview_options=preview,
            reply_to_message_id=reply_to,
            disable_notification=True,
        )
        return True
    except Exception:
        logger.exception("send_message failed in chat %s", chat_id)
        return False


async def send_photo(context, chat_id):
    if not os.path.exists(IMAGE_FILE):
        await context.bot.send_message(chat_id=chat_id, text="Image not found.")
        return
    with open(IMAGE_FILE, "rb") as img:
        await context.bot.send_photo(chat_id=chat_id, photo=img)


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

# ── Command handlers ───────────────────────────────────────────────────────────

async def _cmd_photo(msg, parts, context, chat_id):
    await send_photo(context, chat_id)


async def _cmd_about(msg, parts, context, chat_id):
    await send_about(context, msg)


async def _cmd_providers(msg, parts, context, chat_id):
    await msg.reply_text(providers_text(chat_id))


async def _cmd_status(msg, parts, context, chat_id):
    await msg.reply_text(status_text(chat_id))


async def _cmd_enable(msg, parts, context, chat_id):
    update_chat_setting(chat_id, "enabled", 1)
    await msg.reply_text("Bot enabled in this chat.")


async def _cmd_disable(msg, parts, context, chat_id):
    update_chat_setting(chat_id, "enabled", 0)
    await msg.reply_text("Bot disabled in this chat.")


async def _cmd_muteuser(msg, parts, context, chat_id):
    target = target_user_id_from_command(msg, parts)
    if not target:
        await msg.reply_text("Reply to a user or pass a numeric user id.")
        return
    mute_user(chat_id, target)
    await msg.reply_text(f"Muted user {target}.")


async def _cmd_unmuteuser(msg, parts, context, chat_id):
    target = target_user_id_from_command(msg, parts)
    if not target:
        await msg.reply_text("Reply to a user or pass a numeric user id.")
        return
    unmute_user(chat_id, target)
    await msg.reply_text(f"Unmuted user {target}.")


async def _cmd_resetproviders(msg, parts, context, chat_id):
    reset_providers(chat_id)
    await msg.reply_text("Providers reset to defaults.")


async def _cmd_setprovider(msg, parts, context, chat_id):
    if len(parts) != 3:
        await msg.reply_text("Usage: /setprovider platform provider")
        return
    plat, prov = parts[1].lower(), parts[2].lower()
    if plat not in PROVIDERS:
        await msg.reply_text("Unknown platform. Try /providers")
        return
    if prov not in PROVIDERS[plat]["options"]:
        await msg.reply_text("Unknown provider. Options: " + ", ".join(PROVIDERS[plat]["options"]))
        return
    set_choice(chat_id, plat, prov)
    await msg.reply_text(f"Set {plat} to {prov}.")


async def _cmd_setsendermode(msg, parts, context, chat_id):
    if len(parts) != 2 or parts[1] not in ("first_name", "username", "full_name", "none"):
        await msg.reply_text("Usage: /setsendermode first_name|username|full_name|none")
        return
    update_chat_setting(chat_id, "sender_mode", parts[1])
    await msg.reply_text(f"sender_mode set to {parts[1]}.")


async def _cmd_setdedup(msg, parts, context, chat_id):
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply_text("Usage: /setdedup 60")
        return
    value = max(5, min(3600, int(parts[1])))
    update_chat_setting(chat_id, "dedup_window", value)
    await msg.reply_text(f"dedup_window set to {value}s.")


async def _cmd_setratelimit(msg, parts, context, chat_id):
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.reply_text("Usage: /setratelimit 5 30")
        return
    count = max(1, min(50, int(parts[1])))
    window = max(5, min(3600, int(parts[2])))
    update_chat_setting(chat_id, "rate_limit", count)
    update_chat_setting(chat_id, "rate_window", window)
    await msg.reply_text(f"rate_limit set to {count} per {window}s.")


async def _cmd_ignoreforwards(msg, parts, context, chat_id):
    if len(parts) != 2:
        await msg.reply_text("Usage: /ignoreforwards on|off")
        return
    value = parse_on_off(parts[1])
    if value is None:
        await msg.reply_text("Usage: /ignoreforwards on|off")
        return
    update_chat_setting(chat_id, "ignore_forwards", value)
    await msg.reply_text(f"ignore_forwards set to {bool(value)}.")


async def _cmd_fallback(msg, parts, context, chat_id):
    if len(parts) != 2:
        await msg.reply_text("Usage: /fallback on|off")
        return
    value = parse_on_off(parts[1])
    if value is None:
        await msg.reply_text("Usage: /fallback on|off")
        return
    update_chat_setting(chat_id, "provider_fallback", value)
    await msg.reply_text(f"provider_fallback set to {bool(value)}.")


async def _cmd_textspam(msg, parts, context, chat_id):
    if len(parts) != 2:
        await msg.reply_text("Usage: /textspam on|off")
        return
    value = parse_on_off(parts[1])
    if value is None:
        await msg.reply_text("Usage: /textspam on|off")
        return
    update_chat_setting(chat_id, "text_spam", value)
    await msg.reply_text(f"text_spam set to {bool(value)}.")


async def _cmd_testall(msg, parts, context, chat_id):
    platform = parts[1].lower() if len(parts) > 1 else "instagram"
    custom_url = parts[2] if len(parts) > 2 else None
    if platform not in PROVIDERS:
        await msg.reply_text("Unknown platform. Available: " + ", ".join(sorted(PROVIDERS)))
        return
    base_url = custom_url or SAMPLE_URLS.get(platform)
    if not base_url:
        await msg.reply_text("No sample URL. Pass one: /testall instagram https://...")
        return
    await msg.reply_text(
        f"Testing {len(PROVIDERS[platform]['options'])} providers for {platform}...\n{base_url}"
    )
    for key, host in PROVIDERS[platform]["options"].items():
        parsed = urlparse(base_url)
        fixed = urlunparse((parsed.scheme, host, parsed.path, parsed.params, parsed.query, ""))
        preview = LinkPreviewOptions(
            is_disabled=False,
            url=fixed,
            prefer_large_media=True,
            show_above_text=False,
        )
        try:
            await msg.reply_text(
                f"{PLATFORM_EMOJI.get(platform, '?')} [{key}] {fixed}",
                link_preview_options=preview,
            )
        except Exception:
            logger.exception("/testall failed for %s %s in chat %s", platform, key, chat_id)
            await msg.reply_text(f"[{key}] failed")


# ── Command dispatch maps ──────────────────────────────────────────────────────

PUBLIC_CMDS = {
    "/mehrab": _cmd_photo,
    "/mo": _cmd_photo,
    "/genius": _cmd_photo,
    "/about": _cmd_about,
    "/credits": _cmd_about,
    "/me": _cmd_about,
    "/providers": _cmd_providers,
    "/help": _cmd_providers,
    "/status": _cmd_status,
    "/config": _cmd_status,
}

ADMIN_CMDS = {
    "/enable": _cmd_enable,
    "/disable": _cmd_disable,
    "/muteuser": _cmd_muteuser,
    "/unmuteuser": _cmd_unmuteuser,
    "/resetproviders": _cmd_resetproviders,
    "/setprovider": _cmd_setprovider,
    "/setsendermode": _cmd_setsendermode,
    "/setdedup": _cmd_setdedup,
    "/setratelimit": _cmd_setratelimit,
    "/ignoreforwards": _cmd_ignoreforwards,
    "/fallback": _cmd_fallback,
    "/textspam": _cmd_textspam,
    "/testall": _cmd_testall,
}

# ── Main text handler ──────────────────────────────────────────────────────────
async def handle_message(update, context):
    msg = update.message
    if not msg or not msg.text:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    chat_settings = get_chat_settings(chat_id)
    text = msg.text.strip()

    if is_user_muted(chat_id, user_id):
        await safe_delete(msg, "muted-user")
        return

    if chat_settings["ignore_forwards"] and is_forwarded(msg):
        return

    if text.startswith("/"):
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()

        if cmd in PUBLIC_CMDS:
            await PUBLIC_CMDS[cmd](msg, parts, context, chat_id)
            return

        if cmd in ADMIN_CMDS:
            if not await is_admin(context, chat_id, user_id, msg.chat.type):
                await msg.reply_text("Only admins can use that command.")
                return
            await ADMIN_CMDS[cmd](msg, parts, context, chat_id)
            return

        return

    if not chat_settings["enabled"]:
        return

    if not check_rate(chat_id, user_id, int(chat_settings["rate_limit"]), int(chat_settings["rate_window"])):
        logger.info("Rate limited user %s in chat %s", user_id, chat_id)
        return

    if chat_settings["text_spam"] and len(text) >= 4 and not URL_RE.search(text):
        if seen_recent("text", chat_id, text.lower(), int(chat_settings["dedup_window"])):
            await safe_delete(msg, "duplicate-text")
            return

    new_text, changed, first_fixed_url = await process_text(text, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else None
    post_text = format_repost_text(msg.from_user, new_text, chat_settings["sender_mode"], platform=_detected_platform(new_text))
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_fixed_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed link in chat %s for user %s", chat_id, user_id)
    deleted = await safe_delete(msg, "link-rewrite")
    if deleted:
        await safe_send_text(context, chat_id, post_text, preview=preview, reply_to=reply_to)
    else:
        try:
            await msg.reply_text(post_text, link_preview_options=preview)
            logger.info("Delete failed, replied instead in chat %s", chat_id)
        except Exception:
            logger.exception("reply_text fallback failed in chat %s", chat_id)

# ── Caption handler ────────────────────────────────────────────────────────────
async def handle_caption(update, context):
    msg = update.message
    if not msg or not msg.caption:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    chat_settings = get_chat_settings(chat_id)

    if not chat_settings["enabled"]:
        return
    if is_user_muted(chat_id, user_id):
        await safe_delete(msg, "muted-user-caption")
        return
    if chat_settings["ignore_forwards"] and is_forwarded(msg):
        return
    if not check_rate(chat_id, user_id, int(chat_settings["rate_limit"]), int(chat_settings["rate_window"])):
        return

    new_caption, changed, first_fixed_url = await process_text(msg.caption, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else msg.message_id
    clean_text = format_repost_text(msg.from_user, new_caption, chat_settings["sender_mode"], platform=_detected_platform(new_caption))
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_fixed_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed caption link in chat %s for user %s", chat_id, user_id)
    try:
        await msg.reply_text(clean_text, link_preview_options=preview, reply_to_message_id=reply_to)
    except Exception:
        logger.exception("Caption reply failed in chat %s", chat_id)

# ── Media spam handler ─────────────────────────────────────────────────────────
async def handle_media(update, context):
    msg = update.message
    if not msg:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    chat_settings = get_chat_settings(chat_id)
    if not chat_settings["enabled"]:
        return
    if is_user_muted(chat_id, user_id):
        await safe_delete(msg, "muted-media")
        return

    fuid = None
    if msg.sticker:
        fuid = msg.sticker.file_unique_id
    elif msg.animation:
        fuid = msg.animation.file_unique_id
    if not fuid:
        return

    if seen_recent("media", chat_id, fuid, int(chat_settings["dedup_window"])):
        await safe_delete(msg, "duplicate-media")

# ── Welcome handler ────────────────────────────────────────────────────────────
async def handle_new_members(update, context):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    try:
        me = await context.bot.get_me()
        if any(member.id == me.id for member in msg.new_chat_members):
            await msg.reply_text(WELCOME_TEXT)
    except Exception:
        logger.exception("Failed sending welcome text in chat %s", msg.chat_id if msg else "?")

# ── Boot ───────────────────────────────────────────────────────────────────────
def validate_env():
    if not TOKEN:
        raise SystemExit(
            "ERROR: BOT_TOKEN environment variable is not set. Add it in Railway variables."
        )


async def periodic_cleanup(context):
    cleanup_db()
    logger.info("Periodic DB cleanup done.")


async def on_startup(app):
    init_db()
    cleanup_db()
    await app.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started. Webhook cleared and database ready.")


async def handle_error(update, context):
    if isinstance(context.error, Conflict):
        logger.warning("Conflict: another instance may be running. Ignoring.")
        return
    logger.exception("Unhandled exception for update %s", update, exc_info=context.error)


def main():
    validate_env()
    app = Application.builder().token(TOKEN).post_init(on_startup).build()
    app.add_error_handler(handle_error)
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.VIDEO | filters.Document.ALL) & filters.CaptionRegex(r"https?://"),
            handle_caption,
        )
    )
    app.add_handler(MessageHandler(filters.Sticker.ALL | filters.ANIMATION, handle_media))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.job_queue.run_repeating(periodic_cleanup, interval=3600, first=3600)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
