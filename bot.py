import asyncio
import html as _html
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
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 8443))
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

# Tracking params safe to strip from ANY link (e.g. YouTube), unlike TRACKING
# this deliberately excludes ambiguous keys like "s"/"ref" that legitimate
# sites use for search and routing.
GENERIC_TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "utm_id", "utm_name", "utm_reader", "utm_social", "utm_brand",
    "fbclid", "gclid", "dclid", "msclkid", "yclid", "twclid", "ttclid",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi", "vero_id", "wickedid",
    "igsh", "igshid", "si", "feature",
}

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
SHORTS_RE = re.compile(r"^/shorts/([A-Za-z0-9_-]+)")
TAIL = ".,!?)]>}"
FIXER_HOSTS = {host for cfg in PROVIDERS.values() for host in cfg["options"].values()}
HEALTH_CACHE: dict = {}
HEALTH_TTL = 300
SEEN_UPDATES: OrderedDict = OrderedDict()
MAX_SEEN_UPDATES = 2000
_known_chats: set = set()


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
    "<b>💖 About this bot</b>\n\n"
    "My name is Mehrab and I love you Motki 🥰\n\n"
    "This bot fixes social media links so they embed properly in Telegram. "
    "It can also reduce repeated link, text, sticker, and GIF spam in groups.\n\n"
    "<i>Made with love by Mehrab</i> 💖"
)

WELCOME_TEXT = (
    "👋 Hi! I fix social media links so Telegram previews work properly.\n\n"
    "📷 Instagram · 🐦 Twitter/X · 🎵 TikTok · 🤖 Reddit · and more\n\n"
    "I'll automatically rewrite links as they're posted. "
    "Admins can configure me with /providers and /status."
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


def _warm_chat_cache():
    conn = db_connect()
    for row in conn.execute("SELECT chat_id FROM chat_settings").fetchall():
        _known_chats.add(row["chat_id"])



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
    _warm_chat_cache()


def ensure_chat_settings(chat_id):
    if chat_id in _known_chats:
        return
    conn = db_connect()
    cols = ", ".join(DEFAULT_CHAT_SETTINGS.keys())
    qs = ", ".join(["?"] * len(DEFAULT_CHAT_SETTINGS))
    conn.execute(
        f"INSERT OR IGNORE INTO chat_settings(chat_id, {cols}) VALUES (?, {qs})",
        [chat_id, *DEFAULT_CHAT_SETTINGS.values()],
    )
    conn.commit()
    _known_chats.add(chat_id)


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


def get_muted_user_ids(chat_id):
    conn = db_connect()
    rows = conn.execute(
        "SELECT user_id FROM blocked_users WHERE chat_id = ?", (chat_id,)
    ).fetchall()
    return [r["user_id"] for r in rows]



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


def strip_generic_tracking(url):
    """Remove known tracking params from any URL, preserving everything else
    (path, fragment, and non-tracking query params)."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k.lower() not in GENERIC_TRACKING
    }
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params,
         urlencode(kept, doseq=True), parsed.fragment)
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
    options = PROVIDERS[platform]["options"]
    chosen_url = apply_provider(original_url, platform, preferred_key)
    if not allow_fallback or len(options) == 1:
        return chosen_url, preferred_key
    ordered = [preferred_key] + [k for k in options if k != preferred_key]
    urls = [apply_provider(original_url, platform, k) for k in ordered]
    alive = await asyncio.gather(*[provider_alive(u) for u in urls])
    for key, url, is_alive in zip(ordered, urls, alive):
        if is_alive:
            return url, key
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
        # Not a rewritable platform, but still strip tracking junk
        # (e.g. YouTube ?si=, generic utm_*/fbclid params).
        cleaned = strip_generic_tracking(url)
        if cleaned != url:
            return cleaned + tail, None, url
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
    first_platform = None
    dedup_window = int(chat_settings["dedup_window"])
    for raw in urls:
        fixed, platform, original = await fix_url(raw, chat_id, chat_settings)
        if fixed != raw:
            if original and seen_recent("fix", chat_id, strip_tracking(original), dedup_window):
                continue
            new_text = new_text.replace(raw, fixed)
            changed = True
            if not first_fixed_url:
                first_fixed_url = fixed.split()[0]
                first_platform = platform
    return new_text, changed, first_fixed_url, first_platform


def sender_label(user, mode):
    if not user or mode == "none":
        return None
    if mode == "username" and user.username:
        return "@" + user.username
    if mode == "full_name":
        full = " ".join(x for x in [user.first_name, user.last_name] if x)
        return full or user.first_name or "User"
    return user.first_name or user.username or "User"


def format_repost_text(user, mode, platform=None, url=None):
    label = sender_label(user, mode)
    emoji = PLATFORM_EMOJI.get(platform, "") if platform else ""
    if label and url:
        return f'{emoji} <a href="{url}">{_html.escape(label)}</a>'.strip()
    if label:
        return f"{emoji} {label}".strip() if emoji else label
    return url or ""


def providers_text(chat_id):
    lines = ["<b>Providers</b>", ""]
    for plat in sorted(PROVIDERS):
        cur = get_choice(chat_id, plat)
        emoji = PLATFORM_EMOJI.get(plat, "▪️")
        opt_list = [f"<b>{k}</b>" if k == cur else k for k in PROVIDERS[plat]["options"]]
        lines.append(f"{emoji} <b>{plat}</b>  {' · '.join(opt_list)}")
    lines += [
        "",
        "<b>Admin commands</b>",
        "/setprovider &lt;platform&gt; &lt;provider&gt;",
        "/resetproviders",
        "/enable  ·  /disable",
        "/muteuser  ·  /unmuteuser",
        "/setsendermode first_name|username|full_name|none",
        "/setdedup &lt;seconds&gt;",
        "/setratelimit &lt;count&gt; &lt;seconds&gt;",
        "/ignoreforwards on|off  ·  /fallback on|off  ·  /textspam on|off",
        "/testall &lt;platform&gt;",
        "",
        "<b>Public</b>  /status · /about · /start · /help",
    ]
    return "\n".join(lines)


def status_text(chat_id):
    s = get_chat_settings(chat_id)
    on = lambda v: "✅" if v else "❌"
    rows = [
        ("🤖 Bot",            on(s["enabled"])),
        ("👤 Sender mode",    f"<code>{s['sender_mode']}</code>"),
        ("⏱ Dedup window",   f"<code>{s['dedup_window']}s</code>"),
        ("🚦 Rate limit",     f"<code>{s['rate_limit']}</code> per <code>{s['rate_window']}s</code>"),
        ("↩️ Ignore fwds",    on(s["ignore_forwards"])),
        ("🔄 Fallback",       on(s["provider_fallback"])),
        ("🗑 Text spam",      on(s["text_spam"])),
        ("🔇 Muted users",    f"<code>{blocked_user_count(chat_id)}</code>"),
    ]
    lines = ["<b>Chat status</b>", ""]
    for label, value in rows:
        lines.append(f"{label}  {value}")
    return "\n".join(lines)


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


async def safe_send_text(context, chat_id, text, preview=None, reply_to=None, parse_mode="HTML"):
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            link_preview_options=preview,
            reply_to_message_id=reply_to,
            disable_notification=True,
            parse_mode=parse_mode,
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
                parse_mode="HTML",
            )
    else:
        await msg.reply_text(ABOUT_TEXT, parse_mode="HTML")

# ── Command handlers ───────────────────────────────────────────────────────────

async def _cmd_photo(msg, parts, context, chat_id):
    await send_photo(context, chat_id)


async def _cmd_about(msg, parts, context, chat_id):
    await send_about(context, msg)


async def _cmd_start(msg, parts, context, chat_id):
    if msg.chat.type == "private":
        platforms = " · ".join(
            f"{PLATFORM_EMOJI.get(p, '')} {p}" for p in sorted(PROVIDERS)
        )
        await msg.reply_text(
            "<b>KkInstafix</b> — social link fixer\n\n"
            "Send me a link and I'll rewrite it so Telegram shows a proper preview.\n\n"
            f"<b>Supported platforms</b>\n{platforms}\n\n"
            "Add me to a group and I'll fix links automatically.\n"
            "/providers · /status · /about",
            parse_mode="HTML",
        )
    else:
        await msg.reply_text(WELCOME_TEXT)


async def _cmd_providers(msg, parts, context, chat_id):
    await msg.reply_text(providers_text(chat_id), parse_mode="HTML")


async def _cmd_status(msg, parts, context, chat_id):
    await msg.reply_text(status_text(chat_id), parse_mode="HTML")


async def _cmd_enable(msg, parts, context, chat_id):
    update_chat_setting(chat_id, "enabled", 1)
    await msg.reply_text("✅ Bot enabled — links will be fixed in this chat.")


async def _cmd_disable(msg, parts, context, chat_id):
    update_chat_setting(chat_id, "enabled", 0)
    await msg.reply_text("🚫 Bot disabled — links will be left as-is.")


def _user_display(msg, target_id):
    if msg.reply_to_message and msg.reply_to_message.from_user:
        u = msg.reply_to_message.from_user
        name = u.first_name or u.username or str(target_id)
        return f"<b>{_html.escape(name)}</b>"
    return f"<code>{target_id}</code>"


async def _cmd_muteuser(msg, parts, context, chat_id):
    target = target_user_id_from_command(msg, parts)
    if not target:
        await msg.reply_text("Reply to a user or pass a numeric user id.")
        return
    if is_user_muted(chat_id, target):
        await msg.reply_text(f"🔇 {_user_display(msg, target)} is already muted.", parse_mode="HTML")
        return
    mute_user(chat_id, target)
    await msg.reply_text(f"🔇 Muted {_user_display(msg, target)}.", parse_mode="HTML")


async def _cmd_unmuteuser(msg, parts, context, chat_id):
    target = target_user_id_from_command(msg, parts)
    if not target:
        await msg.reply_text("Reply to a user or pass a numeric user id.")
        return
    if not is_user_muted(chat_id, target):
        await msg.reply_text(f"🔊 {_user_display(msg, target)} is not muted.", parse_mode="HTML")
        return
    unmute_user(chat_id, target)
    await msg.reply_text(f"🔊 Unmuted {_user_display(msg, target)}.", parse_mode="HTML")


async def _cmd_resetproviders(msg, parts, context, chat_id):
    changed = []
    for plat in sorted(PROVIDERS):
        cur = get_choice(chat_id, plat)
        default = PROVIDERS[plat]["default"]
        if cur != default:
            emoji = PLATFORM_EMOJI.get(plat, "▪️")
            changed.append(f"{emoji} {plat}  <code>{cur}</code> → <code>{default}</code>")
    reset_providers(chat_id)
    if changed:
        await msg.reply_text(
            "🔄 Providers reset to defaults:\n\n" + "\n".join(changed), parse_mode="HTML"
        )
    else:
        await msg.reply_text("✅ All providers were already at defaults.")


async def _cmd_setprovider(msg, parts, context, chat_id):
    if len(parts) != 3:
        await msg.reply_text("Usage: /setprovider platform provider")
        return
    plat, prov = parts[1].lower(), parts[2].lower()
    if plat not in PROVIDERS:
        available = " · ".join(sorted(PROVIDERS))
        await msg.reply_text(f"Unknown platform.\n\nAvailable: {available}", parse_mode="HTML")
        return
    if prov not in PROVIDERS[plat]["options"]:
        opts = " · ".join(PROVIDERS[plat]["options"])
        await msg.reply_text(
            f"Unknown provider for {plat}.\n\nOptions: {opts}", parse_mode="HTML"
        )
        return
    old = get_choice(chat_id, plat)
    set_choice(chat_id, plat, prov)
    emoji = PLATFORM_EMOJI.get(plat, "▪️")
    await msg.reply_text(
        f"{emoji} <b>{plat}</b>  <code>{old}</code> → <code>{prov}</code>",
        parse_mode="HTML",
    )


async def _cmd_setsendermode(msg, parts, context, chat_id):
    modes = ("first_name", "username", "full_name", "none")
    if len(parts) != 2 or parts[1] not in modes:
        await msg.reply_text("Usage: /setsendermode first_name|username|full_name|none")
        return
    update_chat_setting(chat_id, "sender_mode", parts[1])
    await msg.reply_text(
        f"👤 Sender mode set to <code>{parts[1]}</code>.", parse_mode="HTML"
    )


async def _cmd_setdedup(msg, parts, context, chat_id):
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply_text("Usage: /setdedup 60")
        return
    requested = int(parts[1])
    value = max(5, min(3600, requested))
    update_chat_setting(chat_id, "dedup_window", value)
    note = f" (clamped from {requested})" if value != requested else ""
    await msg.reply_text(f"Dedup window set to <code>{value}s</code>{note}.", parse_mode="HTML")


async def _cmd_setratelimit(msg, parts, context, chat_id):
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.reply_text("Usage: /setratelimit 5 30")
        return
    req_count, req_window = int(parts[1]), int(parts[2])
    count = max(1, min(50, req_count))
    window = max(5, min(3600, req_window))
    update_chat_setting(chat_id, "rate_limit", count)
    update_chat_setting(chat_id, "rate_window", window)
    notes = []
    if count != req_count:
        notes.append(f"count clamped from {req_count}")
    if window != req_window:
        notes.append(f"window clamped from {req_window}s")
    note = f" ({', '.join(notes)})" if notes else ""
    await msg.reply_text(
        f"Rate limit set to <code>{count}</code> links per <code>{window}s</code>{note}.",
        parse_mode="HTML",
    )


async def _cmd_ignoreforwards(msg, parts, context, chat_id):
    if len(parts) != 2 or parse_on_off(parts[1]) is None:
        await msg.reply_text("Usage: /ignoreforwards on|off")
        return
    value = parse_on_off(parts[1])
    update_chat_setting(chat_id, "ignore_forwards", value)
    state = "✅ on — forwarded posts will be ignored" if value else "❌ off — forwarded posts will be processed"
    await msg.reply_text(f"Ignore forwards: {state}.")


async def _cmd_fallback(msg, parts, context, chat_id):
    if len(parts) != 2 or parse_on_off(parts[1]) is None:
        await msg.reply_text("Usage: /fallback on|off")
        return
    value = parse_on_off(parts[1])
    update_chat_setting(chat_id, "provider_fallback", value)
    state = "✅ on — will try backup providers if primary is down" if value else "❌ off — always uses the selected provider"
    await msg.reply_text(f"Provider fallback: {state}.")


async def _cmd_textspam(msg, parts, context, chat_id):
    if len(parts) != 2 or parse_on_off(parts[1]) is None:
        await msg.reply_text("Usage: /textspam on|off")
        return
    value = parse_on_off(parts[1])
    update_chat_setting(chat_id, "text_spam", value)
    state = "✅ on — repeated plain text will be deleted" if value else "❌ off — repeated plain text is allowed"
    await msg.reply_text(f"Text spam filter: {state}.")



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
    emoji = PLATFORM_EMOJI.get(platform, "▪️")
    n = len(PROVIDERS[platform]["options"])
    await msg.reply_text(
        f"{emoji} Testing <b>{n}</b> providers for <b>{platform}</b>\n<code>{base_url}</code>",
        parse_mode="HTML",
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
                f"<code>[{key}]</code> {fixed}",
                link_preview_options=preview,
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("/testall failed for %s %s in chat %s", platform, key, chat_id)
            await msg.reply_text(f"<code>[{key}]</code> ❌ failed", parse_mode="HTML")


async def _cmd_listmuted(msg, parts, context, chat_id):
    muted = get_muted_user_ids(chat_id)
    if not muted:
        await msg.reply_text("No muted users in this chat.")
        return
    lines = [f"<b>Muted users ({len(muted)})</b>", ""]
    for uid in muted:
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            name = member.user.first_name or member.user.username or str(uid)
            lines.append(f"• 🔇 {_html.escape(name)} — <code>{uid}</code>")
        except Exception:
            lines.append(f"• 🔇 <code>{uid}</code>")
    await msg.reply_text("\n".join(lines), parse_mode="HTML")


HELP_TEXT = (
    "<b>KkInstafix — command reference</b>\n\n"
    "<b>Anyone</b>\n"
    "/start — welcome message\n"
    "/providers — current providers for each platform\n"
    "/status — current chat settings\n"
    "/about — credits\n\n"
    "<b>Admins only</b>\n"
    "/enable · /disable — turn the bot on or off\n"
    "/setprovider &lt;platform&gt; &lt;key&gt; — change provider\n"
    "/resetproviders — restore all defaults\n"
    "/muteuser · /unmuteuser — mute/unmute by reply or user ID\n"
    "/listmuted — list all muted users\n"
    "/setsendermode first_name|username|full_name|none\n"
    "/setdedup &lt;seconds&gt; — dedup window (5–3600)\n"
    "/setratelimit &lt;n&gt; &lt;seconds&gt; — rate limit per user\n"
    "/ignoreforwards on|off\n"
    "/fallback on|off — try backup providers if primary is down\n"
    "/textspam on|off — delete repeated plain-text messages\n"
    "/testall &lt;platform&gt; [url] — test every provider side-by-side"
)


async def _cmd_help(msg, parts, context, chat_id):
    await msg.reply_text(HELP_TEXT, parse_mode="HTML")


# ── Command dispatch maps ──────────────────────────────────────────────────────

PUBLIC_CMDS = {
    "/start": _cmd_start,
    "/mehrab": _cmd_photo,
    "/mo": _cmd_photo,
    "/genius": _cmd_photo,
    "/about": _cmd_about,
    "/credits": _cmd_about,
    "/me": _cmd_about,
    "/providers": _cmd_providers,
    "/help": _cmd_help,
    "/status": _cmd_status,
    "/config": _cmd_status,
}

ADMIN_CMDS = {
    "/enable": _cmd_enable,
    "/disable": _cmd_disable,
    "/muteuser": _cmd_muteuser,
    "/unmuteuser": _cmd_unmuteuser,
    "/listmuted": _cmd_listmuted,
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

    has_url = bool(URL_RE.search(text))

    if not has_url:
        if chat_settings["text_spam"] and len(text) >= 4:
            if seen_recent("text", chat_id, text.lower(), int(chat_settings["dedup_window"])):
                await safe_delete(msg, "duplicate-text")
        return

    if not check_rate(chat_id, user_id, int(chat_settings["rate_limit"]), int(chat_settings["rate_window"])):
        logger.info("Rate limited user %s in chat %s", user_id, chat_id)
        return

    new_text, changed, first_fixed_url, platform = await process_text(text, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else None
    post_text = format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_fixed_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed link in chat %s for user %s", chat_id, user_id)
    deleted = await safe_delete(msg, "link-rewrite")
    if deleted:
        sent = await safe_send_text(context, chat_id, post_text, preview=preview, reply_to=reply_to)
        if not sent:
            await safe_send_text(context, chat_id, post_text, reply_to=reply_to)
    else:
        try:
            await msg.reply_text(post_text, link_preview_options=preview, parse_mode="HTML")
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

    new_caption, changed, first_fixed_url, platform = await process_text(msg.caption, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else msg.message_id
    clean_text = format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_fixed_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed caption link in chat %s for user %s", chat_id, user_id)
    try:
        await msg.reply_text(clean_text, link_preview_options=preview, reply_to_message_id=reply_to, parse_mode="HTML")
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
        if any(member.id == context.bot.id for member in msg.new_chat_members):
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
    if not WEBHOOK_URL:
        await app.bot.delete_webhook(drop_pending_updates=True)
    mode = "webhook" if WEBHOOK_URL else "polling"
    logger.info("Bot started in %s mode. Database ready.", mode)


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
    if WEBHOOK_URL:
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True,
        )
    else:
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
