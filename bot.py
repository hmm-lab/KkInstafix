import asyncio
import html as _html
import io
import json
import logging
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from collections import OrderedDict, deque
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from telegram import (
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions,
)
from telegram.error import Conflict
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

__version__ = "1.36.0"

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
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
PORT = int(os.environ.get("PORT", 8443))
IMAGE_FILE = "30364.jpg"
GENIUS_VIDEO = "genius.mp4"
# Set DATA_DIR to a Railway persistent volume mount (e.g. /data) so settings,
# stats and undo records survive redeploys. Defaults to the working directory.
DB_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "bot_data.sqlite3")
_start_time = time.time()

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
            "xcancel": "xcancel.com",
        },
        # noauth_embed: when one of these keys is chosen, use its value as the
        # embed provider for Telegram's preview while keeping the link URL as-is.
        "noauth_embed": {"xcancel": "vx"},
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
            "proxitok": "proxitok.pabloferreiro.es",
        },
        "noauth_embed": {"proxitok": "tnk"},
    },
    "reddit": {
        "default": "vx",
        "domains": ["reddit.com"],
        "options": {
            "vx": "vxreddit.com",
            "rx": "rxddit.com",
            "rxy": "rxyddit.com",
            "ez": "redditez.com",
            "redlib": "redlib.org",
        },
        "noauth_embed": {"redlib": "vx"},
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
        "domains": ["threads.net", "threads.com"],
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
            "bskye": "bskye.app",
            "xbsky": "xbsky.app",
            "fx": "fxbsky.app",
            "vx": "vxbsky.app",
            "cbsky": "cbsky.app",
        },
    },
    "pixiv": {
        "default": "ph",
        "domains": ["pixiv.net"],
        "options": {"ph": "phixiv.net", "pp": "ppxiv.net"},
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
    "dribbble": {
        "default": "tv",
        "domains": ["dribbble.com"],
        "options": {"tv": "dribbbletv.com"},
    },
}

TRACKING = [
    "igsh", "igshid", "utm_source", "utm_medium", "utm_campaign",
    "utm_content", "utm_term", "utm_id", "fbclid", "ref", "hl", "s", "si",
]
_TRACKING_SET = {t.lower() for t in TRACKING}

# Extra tracking params stripped only for a specific platform when rewriting.
# These keys are unambiguous tracking on their platform but are meaningful
# elsewhere (e.g. "t" is a YouTube timestamp), so they must not go in the global
# TRACKING list. The embed providers need only the path, so dropping these is
# always safe for a rewritten link.
PLATFORM_TRACKING = {
    # Twitter/X share tokens: ?s=20&t=<token>, plus cxt context blobs.
    "twitter": {"t", "cxt"},
    # TikTok app/web session and referrer junk.
    "tiktok": {
        "is_from_webapp", "sender_device", "sender_web_id", "web_id",
        "_t", "_r", "_d", "share_app_id", "share_link_id", "u_code",
        "preview_pb", "refer", "referer_url", "referer_video_id",
    },
}

# Tracking params safe to strip from ANY link (e.g. YouTube), unlike TRACKING
# this deliberately excludes ambiguous keys like "s"/"ref" that legitimate
# sites use for search and routing.
GENERIC_TRACKING = {
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "utm_id", "utm_name", "utm_reader", "utm_social", "utm_brand",
    "fbclid", "gclid", "dclid", "msclkid", "yclid", "twclid", "ttclid",
    "mc_cid", "mc_eid", "_hsenc", "_hsmi", "vero_id", "wickedid",
    "igsh", "igshid", "si",
    # Facebook/Meta mobile share identifiers
    "mibextid", "extid",
    # Reddit web tracking
    "rdt",
    # Campaign / analytics identifiers (unambiguous, vendor-documented)
    "ncid", "cmpid", "_branch_referrer", "oly_enc_id", "oly_anon_id",
}

# YouTube-only share/analytics params. "si" is already in GENERIC_TRACKING so
# it is stripped globally; "is" and "pp" are too generic to strip from arbitrary
# sites, so they are only removed when the host is YouTube. "feature" is a
# documented YouTube share param that could be a legitimate flag elsewhere.
YOUTUBE_HOSTS = {"youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com"}
YOUTUBE_TRACKING = {"is", "feature", "pp"}

# Amazon operates under many country TLDs; track all of them by this set.
AMAZON_TLDS = {
    "amazon.com", "amazon.co.uk", "amazon.de", "amazon.fr", "amazon.co.jp",
    "amazon.ca", "amazon.com.au", "amazon.in", "amazon.it", "amazon.es",
    "amazon.com.br", "amazon.com.mx", "amazon.nl", "amazon.se", "amazon.sg",
    "amazon.ae", "amazon.sa",
    # Additional regional stores
    "amazon.com.tr", "amazon.com.be", "amazon.pl", "amazon.eg", "amazon.co.za",
}
AMAZON_TRACKING = {
    "tag", "ref", "linkCode", "camp", "creative", "creativeASIN",
    "linkId", "th", "psc", "sprefix", "crid", "qid", "sr", "keywords",
    "ie", "hvadid", "hvpos", "hvnetw", "hvrand", "hvdev", "hvtargid",
}
AMAZON_PATH_RE = re.compile(
    r"/(?:dp|gp/product|gp/aw/d|gp/offer-listing|exec/obidos/ASIN|o/ASIN)/([A-Z0-9]{10})",
    re.IGNORECASE,
)

EBAY_TLDS = {
    "ebay.com", "ebay.co.uk", "ebay.de", "ebay.com.au", "ebay.fr",
    "ebay.it", "ebay.es", "ebay.ca", "ebay.com.sg",
    "ebay.at", "ebay.pl", "ebay.nl", "ebay.ch", "ebay.se", "ebay.be",
}
EBAY_TRACKING = {
    "hash", "mkrid", "siteid", "campid", "toolid", "customid",
    "mkcid", "mkevt", "mkpid", "epid", "nma", "ch", "var", "widget_ver",
}

ALIEXPRESS_DOMAINS = {
    "aliexpress.com", "aliexpress.us", "aliexpress.ru",
    "aliexpress.fr", "aliexpress.de", "aliexpress.es", "aliexpress.it",
    "aliexpress.co.uk", "aliexpress.com.br", "aliexpress.nl", "aliexpress.pl",
    "aliexpress.at", "aliexpress.ch", "aliexpress.se", "aliexpress.be",
}
ALIEXPRESS_TRACKING = {
    "spm", "aff_platform", "aff_trace_key", "algo_expid", "algo_pvid",
    "btsid", "ws_ab_test", "pvid", "pdp_npi", "gatewayAdapt",
}

LINKEDIN_TRACKING = {
    "trackingId", "lipi", "src", "trk", "rcm", "refId",
    "midToken", "midSig", "trkInfo", "original_referer",
    "sessionRedirect", "liuid", "midMgmt",
}

PINTEREST_DOMAINS = {
    "pinterest.com", "pinterest.co.uk", "pinterest.de", "pinterest.fr",
    "pinterest.es", "pinterest.it", "pinterest.com.au", "pinterest.ca",
    "pinterest.at", "pinterest.ch", "pinterest.se", "pinterest.pt",
    "pinterest.nl", "pinterest.be", "pinterest.in", "pinterest.jp",
    "pinterest.ru", "pinterest.mx", "pinterest.nz", "pinterest.ie",
    "pinterest.sg", "pinterest.cz", "pinterest.gr", "pinterest.br",
}
PINTEREST_TRACKING = {"rs", "amp"}

APPLE_MUSIC_TRACKING = {"itsct", "itscg", "ls", "app", "at", "ct", "itm_campaign", "itm_content"}

VIMEO_TRACKING = {"app_id", "referrer", "from", "badge"}

SOUNDCLOUD_TRACKING = {"ref", "in"}  # "si" already in GENERIC_TRACKING; "ref" is not (ambiguous globally)

# Pre-built host → extra tracking params map used by strip_generic_tracking.
# Built once at import; O(1) lookup per call instead of 10 sequential if-blocks.
HOST_TRACKING_MAP: dict[str, frozenset] = {}
for _h in YOUTUBE_HOSTS:
    HOST_TRACKING_MAP[_h] = YOUTUBE_TRACKING
for _h in AMAZON_TLDS:
    HOST_TRACKING_MAP[_h] = AMAZON_TRACKING
for _h in EBAY_TLDS:
    HOST_TRACKING_MAP[_h] = EBAY_TRACKING
for _h in ALIEXPRESS_DOMAINS:
    HOST_TRACKING_MAP[_h] = ALIEXPRESS_TRACKING
HOST_TRACKING_MAP["linkedin.com"] = LINKEDIN_TRACKING
for _h in PINTEREST_DOMAINS:
    HOST_TRACKING_MAP[_h] = PINTEREST_TRACKING
HOST_TRACKING_MAP["music.apple.com"] = APPLE_MUSIC_TRACKING
HOST_TRACKING_MAP["vimeo.com"] = VIMEO_TRACKING
HOST_TRACKING_MAP["soundcloud.com"] = SOUNDCLOUD_TRACKING

URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
# YouTube /shorts/<id> and /live/<id> both normalize to a /watch?v=<id> URL,
# which previews more reliably than the original path form.
YOUTUBE_PATH_RE = re.compile(r"^/(?:shorts|live)/([A-Za-z0-9_-]+)", re.IGNORECASE)
YOUTUBE_WATCH_HOSTS = {"youtube.com", "m.youtube.com"}
# youtu.be/<id> is a pure path rewrite to the canonical watch URL — no network.
YOUTU_BE_PATH_RE = re.compile(r"^/([A-Za-z0-9_-]+)", re.IGNORECASE)
TAIL = ".,!?)]>}"
FIXER_HOSTS = {host for cfg in PROVIDERS.values() for host in cfg["options"].values()}
# Short-link domains that redirect to the real URL before we can fix them
SHORT_LINK_DOMAINS = {
    # Platform-specific short/share links (expanded before rewriting)
    "vm.tiktok.com", "vt.tiktok.com", "redd.it", "b23.tv", "t.co",
    "amzn.to",          # Amazon short links
    "maps.app.goo.gl",  # Google Maps
    "pin.it",           # Pinterest
    # Generic URL shorteners (expand to real URL, then apply tracking strip / rewrite)
    "bit.ly", "tinyurl.com", "t.ly", "ow.ly", "is.gd",
    "rb.gy", "buff.ly", "goo.gl",
}
_expand_cache: OrderedDict = OrderedDict()  # short URL -> expanded URL (LRU)
_EXPAND_CACHE_MAX = 2000
HEALTH_CACHE: dict = {}
HEALTH_TTL = 600
SEEN_UPDATES: OrderedDict = OrderedDict()
MAX_SEEN_UPDATES = 2000
_known_chats: set = set()
_settings_cache: dict = {}   # chat_id -> settings dict
_providers_cache: dict = {}  # chat_id -> {platform -> provider_key}
_muted_cache: dict = {}      # chat_id -> set of muted user_ids
_recent_mem: dict = {}       # (kind, chat_id, event_key) -> float timestamp
# Hard cap so the dedup cache stays bounded even if the periodic cleanup job is
# never scheduled (e.g. job-queue extra missing) or hasn't run yet.
_RECENT_MEM_HARD_CAP = 200_000
_file_id_cache: dict = {}    # filename -> telegram file_id
_admin_cache: dict = {}      # (chat_id, user_id) -> (is_admin, expiry_ts)
_user_names: dict = {}       # user_id -> first_name (from messages)
_ADMIN_CACHE_TTL = 300

DEFAULT_CHAT_SETTINGS = {
    "enabled": 1,
    "sender_mode": "first_name",
    "dedup_window": 60,
    "rate_limit": 5,
    "rate_window": 30,
    "ignore_forwards": 1,
    "provider_fallback": 1,
    "text_spam": 1,
}

RATE_LIMIT = 5       # links per user per window
RATE_WINDOW = 30     # seconds

PLATFORM_EMOJI = {
    "instagram": "📷",
    "twitter": "🐦",
    "tiktok": "🎵",
    "reddit": "👽",
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
    "dribbble": "🏀",
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
    "snapchat": "https://www.snapchat.com/spotlight/test",
    "ifunny": "https://ifunny.co/video/test",
    "furaffinity": "https://www.furaffinity.net/view/12345678/",
    "deviantart": "https://www.deviantart.com/test/art/test-12345",
    "dribbble": "https://dribbble.com/shots/12345678-Example-Shot",
}

ABOUT_TEXT = (
    "💖 *About this bot*\n\n"
    "My name is Mehrab and I love you Motki 🥰\n\n"
    "This bot fixes social media links so they embed properly in Telegram. "
    "It can also reduce repeated link, text, sticker, and GIF spam in groups.\n\n"
    "_Made with love by Mehrab_ 💖"
)

WELCOME_TEXT = (
    "👋 <b>Hi! I'm KkInstafix.</b>\n\n"
    "I automatically rewrite social media links so Telegram shows proper previews, "
    "and strip tracking from Amazon, eBay, AliExpress, LinkedIn, and other sites.\n\n"
    "<b>Just send or post a link and I'll fix it automatically.</b>\n\n"
    "Admins: use /menu to configure providers, /help for all commands."
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
    for row in conn.execute("SELECT * FROM chat_settings").fetchall():
        cid = row["chat_id"]
        _known_chats.add(cid)
        _settings_cache[cid] = dict(row)
        _providers_cache[cid] = {p: cfg["default"] for p, cfg in PROVIDERS.items()}


def _warm_providers_cache():
    conn = db_connect()
    for row in conn.execute("SELECT chat_id, platform, provider FROM provider_settings").fetchall():
        cid, plat, prov = row["chat_id"], row["platform"], row["provider"]
        if cid in _providers_cache and plat in PROVIDERS and prov in PROVIDERS[plat]["options"]:
            _providers_cache[cid][plat] = prov


def _warm_muted_cache():
    conn = db_connect()
    for row in conn.execute("SELECT chat_id, user_id FROM blocked_users").fetchall():
        _muted_cache.setdefault(row["chat_id"], set()).add(row["user_id"])


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

        CREATE TABLE IF NOT EXISTS chat_stats (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            sender_id INTEGER NOT NULL DEFAULT 0,
            count INTEGER NOT NULL DEFAULT 0,
            last_ts INTEGER NOT NULL,
            PRIMARY KEY (chat_id, platform, sender_id)
        );

        CREATE TABLE IF NOT EXISTS rewritten_messages (
            chat_id INTEGER NOT NULL,
            bot_msg_id INTEGER NOT NULL,
            original_url TEXT NOT NULL,
            sender_name TEXT,
            ts INTEGER NOT NULL,
            PRIMARY KEY (chat_id, bot_msg_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rewritten_ts ON rewritten_messages(ts);
        """
    )
    _warm_chat_cache()
    _warm_providers_cache()
    _warm_muted_cache()


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
    if chat_id not in _providers_cache:
        _providers_cache[chat_id] = {p: cfg["default"] for p, cfg in PROVIDERS.items()}


def get_chat_settings(chat_id):
    if chat_id in _settings_cache:
        return _settings_cache[chat_id].copy()
    ensure_chat_settings(chat_id)
    conn = db_connect()
    row = conn.execute("SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)).fetchone()
    s = dict(row) if row else DEFAULT_CHAT_SETTINGS.copy()
    _settings_cache[chat_id] = s
    return s.copy()


def update_chat_setting(chat_id, key, value):
    ensure_chat_settings(chat_id)
    conn = db_connect()
    conn.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    if chat_id in _settings_cache:
        _settings_cache[chat_id][key] = value


def update_chat_settings_batch(chat_id, updates: dict):
    ensure_chat_settings(chat_id)
    conn = db_connect()
    for key, value in updates.items():
        conn.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
    conn.commit()
    if chat_id in _settings_cache:
        _settings_cache[chat_id].update(updates)


def get_choice(chat_id, platform):
    chat_p = _providers_cache.get(chat_id)
    if chat_p is not None:
        return chat_p.get(platform, PROVIDERS[platform]["default"])
    # First access for this chat — ensure row exists then cache all platforms
    ensure_chat_settings(chat_id)
    conn = db_connect()
    row = conn.execute(
        "SELECT provider FROM provider_settings WHERE chat_id = ? AND platform = ?",
        (chat_id, platform),
    ).fetchone()
    stored = row["provider"] if row else None
    result = stored if stored and stored in PROVIDERS[platform]["options"] else PROVIDERS[platform]["default"]
    _providers_cache.setdefault(chat_id, {p: cfg["default"] for p, cfg in PROVIDERS.items()})[platform] = result
    return result


def set_choice(chat_id, platform, provider):
    conn = db_connect()
    conn.execute(
        "INSERT OR REPLACE INTO provider_settings(chat_id, platform, provider) VALUES(?, ?, ?)",
        (chat_id, platform, provider),
    )
    conn.commit()
    _providers_cache.setdefault(chat_id, {})[platform] = provider


def reset_providers(chat_id):
    conn = db_connect()
    conn.execute("DELETE FROM provider_settings WHERE chat_id = ?", (chat_id,))
    conn.commit()
    _providers_cache.pop(chat_id, None)


def _muted_set(chat_id) -> set:
    if chat_id not in _muted_cache:
        conn = db_connect()
        rows = conn.execute(
            "SELECT user_id FROM blocked_users WHERE chat_id = ?", (chat_id,)
        ).fetchall()
        _muted_cache[chat_id] = {r["user_id"] for r in rows}
    return _muted_cache[chat_id]


def mute_user(chat_id, user_id):
    conn = db_connect()
    conn.execute(
        "INSERT OR IGNORE INTO blocked_users(chat_id, user_id) VALUES(?, ?)",
        (chat_id, user_id),
    )
    conn.commit()
    _muted_set(chat_id).add(user_id)


def unmute_user(chat_id, user_id):
    conn = db_connect()
    conn.execute(
        "DELETE FROM blocked_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    conn.commit()
    _muted_set(chat_id).discard(user_id)


def is_user_muted(chat_id, user_id):
    return user_id in _muted_set(chat_id)


def blocked_user_count(chat_id):
    return len(_muted_set(chat_id))


def cleanup_db():
    now = int(time.time())
    conn = db_connect()
    conn.execute("DELETE FROM rewritten_messages WHERE ts < ?", (now - 7 * 86400,))
    conn.commit()
    # Prune stale in-memory caches
    cutoff = now - 7200
    for key in [k for k, ts_list in _rate_mem.items() if not ts_list or ts_list[-1] < cutoff]:
        del _rate_mem[key]
    for key in [k for k, v in _recent_mem.items() if v < cutoff]:
        del _recent_mem[key]
    if len(_recent_mem) > 500_000:
        _recent_mem.clear()
    for key in [k for k, (_, exp) in _admin_cache.items() if exp < now]:
        del _admin_cache[key]
    if len(_user_names) > 50_000:
        to_keep = dict(list(_user_names.items())[-10_000:])
        _user_names.clear()
        _user_names.update(to_keep)


def increment_stat(chat_id, platform, sender_id):
    now = int(time.time())
    conn = db_connect()
    conn.execute(
        """
        INSERT INTO chat_stats(chat_id, platform, sender_id, count, last_ts)
        VALUES(?, ?, ?, 1, ?)
        ON CONFLICT(chat_id, platform, sender_id) DO UPDATE SET
            count = count + 1,
            last_ts = excluded.last_ts
        """,
        (chat_id, platform, sender_id, now),
    )
    conn.commit()


def get_stats(chat_id):
    conn = db_connect()
    total = conn.execute(
        "SELECT COALESCE(SUM(count), 0) AS c FROM chat_stats WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()["c"]
    by_platform = conn.execute(
        """
        SELECT platform, SUM(count) AS c FROM chat_stats
        WHERE chat_id = ?
        GROUP BY platform ORDER BY c DESC LIMIT 10
        """,
        (chat_id,),
    ).fetchall()
    by_sender = conn.execute(
        """
        SELECT sender_id, SUM(count) AS c FROM chat_stats
        WHERE chat_id = ? AND sender_id != 0
        GROUP BY sender_id ORDER BY c DESC LIMIT 5
        """,
        (chat_id,),
    ).fetchall()
    return total, by_platform, by_sender


def store_rewrite(chat_id, bot_msg_id, original_url, sender_name):
    now = int(time.time())
    conn = db_connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO rewritten_messages
        (chat_id, bot_msg_id, original_url, sender_name, ts)
        VALUES (?, ?, ?, ?, ?)
        """,
        (chat_id, bot_msg_id, original_url, sender_name, now),
    )
    conn.commit()


def lookup_rewrite(chat_id, bot_msg_id):
    conn = db_connect()
    row = conn.execute(
        "SELECT original_url, sender_name FROM rewritten_messages WHERE chat_id = ? AND bot_msg_id = ?",
        (chat_id, bot_msg_id),
    ).fetchone()
    return (row["original_url"], row["sender_name"]) if row else (None, None)


def export_chat_data(chat_id):
    conn = db_connect()
    settings_row = conn.execute(
        "SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    # Fall back to the default for any key not yet present in the DB row (schema
    # evolution: new settings added after this chat's row was created).
    settings = (
        {k: (settings_row[k] if k in settings_row.keys() else DEFAULT_CHAT_SETTINGS[k])
         for k in DEFAULT_CHAT_SETTINGS}
        if settings_row else DEFAULT_CHAT_SETTINGS.copy()
    )
    providers = {
        row["platform"]: row["provider"]
        for row in conn.execute(
            "SELECT platform, provider FROM provider_settings WHERE chat_id = ?", (chat_id,)
        )
    }
    muted = [
        row["user_id"]
        for row in conn.execute(
            "SELECT user_id FROM blocked_users WHERE chat_id = ?", (chat_id,)
        )
    ]
    return {
        "version": 1,
        "chat_id": chat_id,
        "settings": settings,
        "providers": providers,
        "muted_users": muted,
    }


def import_chat_data(chat_id, data):
    if not isinstance(data, dict) or data.get("version") != 1:
        return False, "unsupported format"
    source_chat = data.get("chat_id")
    settings = data.get("settings", {})
    providers = data.get("providers", {})
    muted = data.get("muted_users", [])
    _INT_BOOL_SETTINGS = {"enabled", "ignore_forwards", "provider_fallback", "text_spam"}
    _INT_POS_SETTINGS = {"dedup_window", "rate_limit", "rate_window"}
    _SENDER_MODES = {"first_name", "username", "full_name", "none"}
    ensure_chat_settings(chat_id)
    conn = db_connect()
    for key, value in settings.items():
        if key not in DEFAULT_CHAT_SETTINGS:
            continue
        if key in _INT_BOOL_SETTINGS:
            if not isinstance(value, int) or value not in (0, 1):
                continue
        elif key in _INT_POS_SETTINGS:
            if not isinstance(value, int) or value < 0:
                continue
        elif key == "sender_mode":
            if value not in _SENDER_MODES:
                continue
        conn.execute(
            f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?",
            (value, chat_id),
        )
    for platform, provider in providers.items():
        if platform in PROVIDERS and provider in PROVIDERS[platform]["options"]:
            conn.execute(
                "INSERT OR REPLACE INTO provider_settings(chat_id, platform, provider) VALUES(?, ?, ?)",
                (chat_id, platform, provider),
            )
    imported_mutes = 0
    for user_id in muted:
        if isinstance(user_id, int):
            conn.execute(
                "INSERT OR IGNORE INTO blocked_users(chat_id, user_id) VALUES(?, ?)",
                (chat_id, user_id),
            )
            imported_mutes += 1
    conn.commit()
    # Invalidate in-memory caches so changes take effect immediately
    _settings_cache.pop(chat_id, None)
    _providers_cache.pop(chat_id, None)
    _muted_cache.pop(chat_id, None)
    msg = f"imported {len(providers)} providers, {imported_mutes} mutes"
    if source_chat and source_chat != chat_id:
        msg += f"\n⚠️ This backup was from a different chat ({source_chat}) — double-check the settings."
    return True, msg


def seen_recent(kind, chat_id, event_key, window):
    now = time.time()
    key = (kind, chat_id, event_key)
    ts = _recent_mem.get(key)
    if ts and now - ts < window:
        return True
    _recent_mem[key] = now
    # Self-contained safety valve: age-based pruning lives in the hourly
    # cleanup_db job, but if that never runs, hard-cap memory by clearing
    # wholesale. O(1) per call; the O(n) clear only fires far above steady state.
    if len(_recent_mem) > _RECENT_MEM_HARD_CAP:
        _recent_mem.clear()
        _recent_mem[key] = now
    return False


_rate_mem: dict = {}  # (chat_id, user_id) -> deque of timestamps


def check_rate(chat_id, user_id, limit_count, window):
    now = time.time()
    key = (chat_id, user_id)
    timestamps = _rate_mem.get(key)
    if timestamps is None:
        timestamps = deque()
        _rate_mem[key] = timestamps
    cutoff = now - window
    while timestamps and timestamps[0] < cutoff:
        timestamps.popleft()
    if len(timestamps) >= limit_count:
        return False
    timestamps.append(now)
    return True

# ── Helpers ────────────────────────────────────────────────────────────────────

def is_duplicate_update(update_id):
    if update_id in SEEN_UPDATES:
        return True
    SEEN_UPDATES[update_id] = None
    if len(SEEN_UPDATES) > MAX_SEEN_UPDATES:
        SEEN_UPDATES.popitem(last=False)
    return False


def strip_tracking(url, extra=None):
    drop = _TRACKING_SET if not extra else _TRACKING_SET | extra
    parsed = urlparse(url)
    kept = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k.lower() not in drop
    }
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(kept, doseq=True), "")
    )


def strip_generic_tracking(url):
    """Remove known tracking params from any URL, preserving everything else
    (path, fragment, and non-tracking query params). On YouTube hosts a few
    extra share params (e.g. ?si=, ?is=) are also dropped."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    host = parsed.netloc.lower().removeprefix("www.")
    drop = set(GENERIC_TRACKING)
    host_extra = HOST_TRACKING_MAP.get(host)
    if host_extra:
        drop |= host_extra
    drop_lower = {d.lower() for d in drop}
    kept = {
        k: v
        for k, v in parse_qs(parsed.query, keep_blank_values=True).items()
        if k.lower() not in drop_lower
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
    if host in YOUTUBE_WATCH_HOSTS and YOUTUBE_PATH_RE.match(path):
        return "youtube_watch"
    for plat, cfg in PROVIDERS.items():
        for dom in cfg["domains"]:
            if host == dom or host.endswith("." + dom):
                return plat
    return None


def apply_provider(url, platform, provider_key):
    host = PROVIDERS[platform]["options"][provider_key]
    parsed = urlparse(url)
    fixed = urlunparse((parsed.scheme, host, parsed.path, parsed.params, parsed.query, ""))
    return strip_tracking(fixed, extra=PLATFORM_TRACKING.get(platform))


def clean_url(url):
    """Strip tracking from a single URL WITHOUT swapping to a fixer host.

    For a known platform this removes the same params a rewrite would (the global
    TRACKING list plus that platform's share tokens), just keeping the original
    host. For everything else it applies the conservative generic strip (which is
    YouTube-aware and preserves fragments). Powers the /clean command.
    """
    parsed = urlparse(url)
    platform = get_platform(parsed.netloc, parsed.path)
    if platform and platform in PROVIDERS:
        return strip_tracking(url, extra=PLATFORM_TRACKING.get(platform))
    return strip_generic_tracking(url)


async def clean_url_expanded(url):
    """Like clean_url but expands short links and applies path rewrites first.

    Powers /clean so that e.g. `/clean bit.ly/xyz` or `/clean youtu.be/abc?si=x`
    returns the expanded, tracking-stripped destination rather than the short URL
    unchanged. Mirrors the transformations fix_url applies before platform detection.
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    # youtu.be: pure path rewrite, no network (same reason as fix_url avoids HTTP).
    if host == "youtu.be":
        m = YOUTU_BE_PATH_RE.match(parsed.path)
        if m:
            watch = "https://www.youtube.com/watch?v=" + m.group(1)
            q = parse_qs(parsed.query)
            for tkey in ("t", "start"):
                if q.get(tkey):
                    watch += f"&{tkey}=" + q[tkey][0]
                    break
            return watch
        return url
    if host in SHORT_LINK_DOMAINS:
        url = await expand_short_url(url)
        parsed = urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
    # Amazon: extract canonical /dp/ASIN path after expansion.
    if host in AMAZON_TLDS:
        m = AMAZON_PATH_RE.search(parsed.path)
        if m:
            return f"{parsed.scheme}://{parsed.netloc}/dp/{m.group(1).upper()}"
    return clean_url(url)


def _check_url_sync(url: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=4):
            return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


_RESTRICTION_PHRASES = [
    "people under 13 can't see this",
    "set limits on who can see",
    "this account is private",
    "this content isn't available",
    "content not available",
    "restricted to",
]


def _is_restricted_sync(url: str) -> bool:
    """Return True if the URL is inaccessible: 4xx HTTP error or known restriction phrases."""
    try:
        # Use Telegram's real preview-crawler UA so we test exactly what
        # Telegram sees; embed providers whitelist this UA.
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "TelegramBot (like TwitterBot)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            chunk = resp.read(3072).decode("utf-8", errors="ignore").lower()
        return any(phrase in chunk for phrase in _RESTRICTION_PHRASES)
    except urllib.error.HTTPError as e:
        # 4xx = content inaccessible (private, age-gated, blocked by provider)
        return 400 <= e.code < 500
    except Exception:
        return False


async def _warn_if_restricted(context, chat_id: int, msg_id: int, check_url: str, original_text: str, preview=None, reply_markup=None):
    """Background task: if the fixed URL is inaccessible, edit the message to explain."""
    loop = asyncio.get_running_loop()
    restricted = await loop.run_in_executor(None, _is_restricted_sync, check_url)
    if not restricted:
        return
    warning = "⚠️ <i>This content isn't accessible — the account may be private, age-restricted, or have limited who can view it.</i>"
    new_text = f"{original_text}\n\n{warning}" if original_text else warning
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=new_text,
            parse_mode="HTML",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            reply_markup=reply_markup,
        )
    except Exception:
        pass


def _expand_short_url_sync(url: str) -> str:
    if url in _expand_cache:
        _expand_cache.move_to_end(url)
        return _expand_cache[url]
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = resp.url
    except urllib.error.HTTPError as e:
        result = getattr(e, "url", None) or url
    except Exception as exc:
        logger.debug("Short-link expansion failed for %s: %s", url, exc)
        result = url
    _expand_cache[url] = result
    if len(_expand_cache) > _EXPAND_CACHE_MAX:
        _expand_cache.popitem(last=False)
    return result


async def expand_short_url(url: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _expand_short_url_sync, url)


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
    r"^/(p|reel|tv|stories|s|share)/",
    re.IGNORECASE,
)


async def fix_url(raw, chat_id, chat_settings):
    url, tail = trim(raw)
    original_url = url  # pre-expansion URL for dedup and non-platform comparison
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    # youtu.be is a pure path rewrite to the canonical watch URL — it must never
    # be expanded over HTTP. From a server IP that redirect can land on a Google
    # CAPTCHA page (google.com/sorry/...), so we rewrite the path directly and
    # drop share/tracking params, keeping only a t/start timestamp.
    if host == "youtu.be":
        m = YOUTU_BE_PATH_RE.match(parsed.path)
        if m:
            watch = "https://www.youtube.com/watch?v=" + m.group(1)
            q = parse_qs(parsed.query)
            for tkey in ("t", "start"):
                if q.get(tkey):
                    watch += f"&{tkey}=" + q[tkey][0]
                    break
            return watch + tail, None, None, None
        return raw, None, None, None
    # Amazon: extract canonical /dp/ASIN path, stripping all referral/affiliate
    # junk. Works for any amazon TLD and for amzn.to links (already expanded).
    if host in AMAZON_TLDS:
        m = AMAZON_PATH_RE.search(parsed.path)
        if m:
            asin = m.group(1).upper()
            canon = f"{parsed.scheme}://{parsed.netloc}/dp/{asin}"
            if canon != original_url:
                return canon + tail, None, canon, canon
        # No ASIN in path — fall through to generic tracking strip
    # Expand short-link and share-link redirects before platform detection.
    # Covers: redd.it/ID, vm.tiktok.com, vt.tiktok.com, b23.tv, t.co, amzn.to,
    # plus path-based share links — Reddit /r/<sub>/s/<id>, TikTok /t/<id>, and
    # Instagram /share/<id> — that all redirect to the canonical post URL. A
    # t.co link unwraps to its target, which is then fixed (if it's a known
    # platform) or tracking-stripped like any other plain link.
    if host in SHORT_LINK_DOMAINS or (
        host == "reddit.com" and re.match(r"^/r/[^/]+/s/", parsed.path, re.IGNORECASE)
    ) or (
        host == "tiktok.com" and re.match(r"^/t/", parsed.path, re.IGNORECASE)
    ) or (
        host == "instagram.com" and re.match(r"^/share/", parsed.path, re.IGNORECASE)
    ):
        url = await expand_short_url(url)
        parsed = urlparse(url)
        host = parsed.netloc.lower().removeprefix("www.")
        # amzn.to expands to a full amazon.* URL — run ASIN extraction now.
        if host in AMAZON_TLDS:
            m = AMAZON_PATH_RE.search(parsed.path)
            if m:
                asin = m.group(1).upper()
                canon = f"{parsed.scheme}://{parsed.netloc}/dp/{asin}"
                if canon != original_url:
                    return canon + tail, None, canon, canon
    platform = get_platform(parsed.netloc, parsed.path)
    if not platform:
        # Not a rewritable platform, but still strip tracking junk
        # (e.g. YouTube ?si=, generic utm_*/fbclid params). Also catches youtu.be
        # expansion: the expanded URL differs from original_url even if no
        # additional params need stripping.
        cleaned = strip_generic_tracking(url)
        if cleaned != original_url:
            return cleaned + tail, None, cleaned, cleaned
        return raw, None, None, None
    if platform == "instagram" and not INSTAGRAM_CONTENT_RE.match(parsed.path):
        return raw, None, None, None
    if platform == "youtube_watch":
        # get_platform already verified YOUTUBE_PATH_RE matches before returning
        # "youtube_watch", so m is always truthy here.
        m = YOUTUBE_PATH_RE.match(parsed.path)
        watch = "https://www.youtube.com/watch?v=" + m.group(1)
        # Preserve a start-time param (t / start) if the original had one.
        q = parse_qs(parsed.query)
        for tkey in ("t", "start"):
            if q.get(tkey):
                watch += f"&{tkey}=" + q[tkey][0]
                break
        return watch + tail, None, None, None
    preferred = get_choice(chat_id, platform)
    allow_fallback = bool(chat_settings.get("provider_fallback", 1))
    noauth_embed = PROVIDERS[platform].get("noauth_embed", {})
    # If a no-account frontend is chosen, skip health-checking the frontend
    # itself (it's just a browser link) and only health-check the embed provider
    # used for Telegram's preview.
    if preferred in noauth_embed:
        fixed = apply_provider(url, platform, preferred)
        embed_key = noauth_embed[preferred]
        embed_fixed, _ = await choose_provider_url(
            url, platform, embed_key,
            allow_fallback=allow_fallback,
        )
        return fixed + tail, platform, url, embed_fixed
    fixed, _ = await choose_provider_url(
        url,
        platform,
        preferred,
        allow_fallback=allow_fallback,
    )
    return fixed + tail, platform, url, fixed


def build_fixed_for_key(original_url, platform, key):
    """Force a specific provider for an original URL, no health check.

    Returns (link_url, preview_url). For no-account frontends the clickable
    link points at the chosen frontend while the preview uses its embed pair.
    Used by the per-message "try another provider" button.
    """
    url, _tail = trim(original_url)
    link = apply_provider(url, platform, key)
    noauth_embed = PROVIDERS[platform].get("noauth_embed", {})
    if key in noauth_embed:
        preview = apply_provider(url, platform, noauth_embed[key])
    else:
        preview = link
    return link, preview


async def process_text(text, chat_id, chat_settings):
    urls = URL_RE.findall(text)
    changed = False
    fixed_count = 0
    first_fixed_url = None
    first_raw_url = None   # raw token in the user's message that maps to first_fixed_url
    first_preview_url = None
    first_platform = None
    fixed_platforms = []
    dedup_window = int(chat_settings["dedup_window"])
    replacements = {}  # exact raw token -> fixed token (only URLs we rewrite)
    for raw in urls:
        if raw in replacements:
            continue  # this exact token already resolved
        fixed, platform, original, preview = await fix_url(raw, chat_id, chat_settings)
        if fixed == raw:
            continue
        # Record the replacement before the dedup check so that two different
        # raw tokens that clean to the same canonical URL (e.g. ?utm_id=1 and
        # ?utm_id=2) both get rewritten in the message text.
        replacements[raw] = fixed
        if original and seen_recent("fix", chat_id, original, dedup_window):
            continue
        changed = True
        fixed_count += 1
        if platform:
            fixed_platforms.append(platform)
        if not first_fixed_url:
            first_fixed_url = fixed.split()[0]
            first_raw_url = raw
            first_preview_url = preview
            first_platform = platform

    if changed:
        # Rewrite each URL token in a single regex pass, matching whole tokens
        # exactly. str.replace() would also clobber substrings — a short URL that
        # is a prefix of a longer one (e.g. ".../p?utm_id=1" inside
        # ".../p?utm_id=1&keep=2") would corrupt the longer link.
        new_text = URL_RE.sub(lambda m: replacements.get(m.group(0), m.group(0)), text)
    else:
        new_text = text
    return new_text, changed, first_fixed_url, first_platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url


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
        # The message is sent with parse_mode=HTML, so the URL must be escaped
        # both for the href attribute (quotes) and HTML entities (&).
        safe_url = _html.escape(url, quote=True)
        return f'{emoji} <a href="{safe_url}">{_html.escape(label)}</a>'.strip()
    if label:
        return f"{emoji} {label}".strip() if emoji else label
    return _html.escape(url) if url else ""


def providers_text(chat_id):
    lines = ["<b>Providers for this chat</b>", ""]
    has_noauth = False
    for plat in sorted(PROVIDERS):
        cur = get_choice(chat_id, plat)
        emoji = PLATFORM_EMOJI.get(plat, "")
        noauth_keys = set(PROVIDERS[plat].get("noauth_embed", {}).keys())
        opts = []
        for key in PROVIDERS[plat]["options"]:
            label = f"✓ <b>{key}</b>" if key == cur else key
            if key in noauth_keys:
                label += " 🌐"
                has_noauth = True
            opts.append(label)
        lines.append(f"{emoji} <b>{plat}</b>: {', '.join(opts)}")
    lines.append("")
    if has_noauth:
        lines.append("🌐 = no-account frontend (Telegram preview still loads via embed provider)")
        lines.append("")
    lines += [
        "Admins: /menu to change providers interactively, or:",
        "<code>/setprovider &lt;platform&gt; &lt;key&gt;</code>",
        "<code>/resetproviders</code> — restore defaults",
    ]
    return "\n".join(lines)


def status_text(chat_id):
    s = get_chat_settings(chat_id)
    on_off = lambda v: "✅ on" if v else "❌ off"
    mode_labels = {
        "first_name": "first name",
        "username": "@username",
        "full_name": "full name",
        "none": "hidden",
    }
    mode = mode_labels.get(s["sender_mode"], s["sender_mode"])
    muted = blocked_user_count(chat_id)
    enabled_line = "✅ <b>Bot is ON</b>" if s["enabled"] else "❌ <b>Bot is OFF</b> — /enable to turn on"
    return "\n".join([
        "<b>Chat status</b>",
        "",
        enabled_line,
        f"Sender label: <code>{mode}</code>",
        f"Dedup window: <code>{s['dedup_window']}s</code>",
        f"Rate limit: <code>{s.get('rate_limit', RATE_LIMIT)} links / {s.get('rate_window', RATE_WINDOW)}s</code>",
        f"Ignore forwards: {on_off(s.get('ignore_forwards', 1))}",
        f"Provider fallback: {on_off(s.get('provider_fallback', 1))}",
        f"Text spam deletion: {on_off(s.get('text_spam', 1))}",
        f"Muted users: <code>{muted}</code>",
    ])


def _build_platform_keyboard(chat_id):
    rows = []
    platforms = sorted(PROVIDERS)
    for i in range(0, len(platforms), 2):
        row = []
        for plat in platforms[i:i + 2]:
            emoji = PLATFORM_EMOJI.get(plat, "")
            cur = get_choice(chat_id, plat)
            row.append(InlineKeyboardButton(f"{emoji} {plat} · {cur}", callback_data=f"m:p:{plat}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("✖ Close", callback_data="m:close")])
    return InlineKeyboardMarkup(rows)


def _cycle_keyboard(platform, next_idx):
    """One-button keyboard that swaps a repost to the next provider.

    next_idx is the index in PROVIDERS[platform]["options"] to switch to on tap.
    """
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🔁 Embed not working?", callback_data=f"e:{platform}:{next_idx}")]]
    )


def _build_provider_keyboard(chat_id, platform):
    current = get_choice(chat_id, platform)
    noauth_keys = set(PROVIDERS[platform].get("noauth_embed", {}).keys())
    rows = []
    options = list(PROVIDERS[platform]["options"])
    for i in range(0, len(options), 3):
        row = []
        for key in options[i:i + 3]:
            mark = "✅ " if key == current else ""
            suffix = " 🌐" if key in noauth_keys else ""
            row.append(InlineKeyboardButton(f"{mark}{key}{suffix}", callback_data=f"m:s:{platform}:{key}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅ Back", callback_data="m:back")])
    return InlineKeyboardMarkup(rows)


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
    now = time.time()
    key = (chat_id, user_id)
    cached = _admin_cache.get(key)
    if cached and cached[1] > now:
        return cached[0]
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        result = member.status in ("administrator", "creator")
    except Exception:
        logger.exception("Failed admin check in chat %s for user %s", chat_id, user_id)
        result = False
    _admin_cache[key] = (result, now + _ADMIN_CACHE_TTL)
    return result


async def safe_delete(msg, reason):
    try:
        await msg.delete()
        logger.info("Deleted message in chat %s (%s)", msg.chat_id, reason)
        return True
    except Exception:
        logger.exception("Delete failed in chat %s (%s)", msg.chat_id, reason)
        return False


async def safe_send_text(context, chat_id, text, preview=None, reply_to=None, parse_mode="HTML", reply_markup=None):
    try:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            link_preview_options=preview,
            reply_to_message_id=reply_to,
            disable_notification=True,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
    except Exception:
        logger.exception("send_message failed in chat %s", chat_id)
        return None


async def send_photo(context, chat_id):
    cached = _file_id_cache.get(IMAGE_FILE)
    if cached:
        await context.bot.send_photo(chat_id=chat_id, photo=cached)
        return
    if not os.path.exists(IMAGE_FILE):
        await context.bot.send_message(chat_id=chat_id, text="Image not found.")
        return
    with open(IMAGE_FILE, "rb") as img:
        sent = await context.bot.send_photo(chat_id=chat_id, photo=img)
    if sent.photo:
        _file_id_cache[IMAGE_FILE] = sent.photo[-1].file_id


async def send_genius_video(context, chat_id):
    cached = _file_id_cache.get(GENIUS_VIDEO)
    if cached:
        await context.bot.send_video(chat_id=chat_id, video=cached)
        return
    if not os.path.exists(GENIUS_VIDEO):
        await context.bot.send_message(chat_id=chat_id, text="Video not found.")
        return
    with open(GENIUS_VIDEO, "rb") as vid:
        sent = await context.bot.send_video(chat_id=chat_id, video=vid)
    if sent.video:
        _file_id_cache[GENIUS_VIDEO] = sent.video.file_id


async def send_about(context, msg):
    if os.path.exists(IMAGE_FILE):
        cached = _file_id_cache.get(IMAGE_FILE + ":about")
        photo_src = cached if cached else open(IMAGE_FILE, "rb")
        try:
            sent = await context.bot.send_photo(
                chat_id=msg.chat_id,
                photo=photo_src,
                caption=ABOUT_TEXT,
                parse_mode="Markdown",
            )
            if not cached and sent.photo:
                _file_id_cache[IMAGE_FILE + ":about"] = sent.photo[-1].file_id
        finally:
            if not cached:
                photo_src.close()
    else:
        await msg.reply_text(ABOUT_TEXT, parse_mode="Markdown")

# ── Command handlers ───────────────────────────────────────────────────────────

async def _cmd_photo(msg, parts, context, chat_id):
    await send_photo(context, chat_id)


async def _cmd_genius(msg, parts, context, chat_id):
    await send_genius_video(context, chat_id)


async def _cmd_about(msg, parts, context, chat_id):
    await send_about(context, msg)


async def _cmd_providers(msg, parts, context, chat_id):
    await msg.reply_text(providers_text(chat_id), parse_mode="HTML")


async def _cmd_help(msg, parts, context, chat_id):
    text = (
        "<b>KkInstafix commands</b>\n\n"
        "<b>📖 Public</b>\n"
        "/providers — active providers for this chat\n"
        "/status — current chat settings\n"
        "/stats — link-fix counts and top senders\n"
        "/undo — reply to a bot message to reveal the original link\n"
        "/clean — strip tracking from a replied link (or /clean &lt;url&gt;); expands short links\n"
        "/about — credits\n"
        "/version — show the bot version\n"
        "/mehrab · /genius — custom image / video\n\n"
        "<b>💬 Inline</b>\n"
        "<code>@KkInstaFixBot &lt;link&gt;</code> — fix a link in any chat without adding the bot\n\n"
        "<b>🔁 Per-message</b>\n"
        "Tap <b>Embed not working?</b> under any fixed link to cycle to a different provider.\n\n"
        "<b>🔧 Admin only</b>\n"
        "/menu — interactive provider picker\n"
        "/enable · /disable — turn the bot on or off\n"
        "<code>/setprovider &lt;platform&gt; &lt;key&gt;</code> — change a provider\n"
        "/resetproviders — restore all defaults\n"
        "/muteuser · /unmuteuser · /listmuted — mute management\n"
        "<code>/setsendermode first_name|username|full_name|none</code>\n"
        "<code>/setdedup &lt;seconds&gt;</code> — dedup window\n"
        "<code>/setratelimit &lt;count&gt; &lt;seconds&gt;</code> — link rate limit\n"
        "<code>/ignoreforwards on|off</code> · <code>/fallback on|off</code> · <code>/textspam on|off</code>\n"
        "/resetstats — clear this chat's stats\n"
        "<code>/testall &lt;platform&gt; [url]</code> — test all providers\n"
        "/export · /import — backup and restore settings\n"
        "/ping — uptime and cache info"
    )
    await msg.reply_text(text, parse_mode="HTML")


async def _cmd_status(msg, parts, context, chat_id):
    await msg.reply_text(status_text(chat_id), parse_mode="HTML")


async def _cmd_version(msg, parts, context, chat_id):
    await msg.reply_text(f"KkInstafix <b>v{__version__}</b>", parse_mode="HTML")


async def _cmd_clean(msg, parts, context, chat_id):
    source = ""
    if msg.reply_to_message:
        source = msg.reply_to_message.text or msg.reply_to_message.caption or ""
    if not source and len(parts) > 1:
        source = " ".join(parts[1:])

    urls = URL_RE.findall(source)
    # Telegram text_link entities store the URL in entity metadata, not in the
    # visible text — regex can't find them.  Fall back to parse_entities().
    if not urls and msg.reply_to_message:
        reply = msg.reply_to_message
        try:
            entity_map = reply.parse_entities(types=["text_link", "url"]) or {}
            for ent, etxt in entity_map.items():
                url = getattr(ent, "url", None) or etxt
                if url and url not in urls:
                    urls.append(url)
        except Exception:
            pass
    if not urls:
        await msg.reply_text(
            "Reply to a message with a link, or use <code>/clean &lt;url&gt;</code>.",
            parse_mode="HTML",
        )
        return

    seen = set()
    cleaned = []
    changed_any = False
    for raw in urls:
        url, _tail = trim(raw)
        stripped = await clean_url_expanded(url)
        if stripped != url:
            changed_any = True
        if stripped not in seen:
            seen.add(stripped)
            cleaned.append(stripped)

    if len(cleaned) == 1:
        preview = LinkPreviewOptions(
            is_disabled=False, url=cleaned[0], prefer_large_media=True, show_above_text=False
        )
    else:
        preview = LinkPreviewOptions(is_disabled=True)

    header = "🧹 Cleaned:" if changed_any else "✅ Already clean:"
    body = "\n".join(cleaned)
    await msg.reply_text(f"{header}\n{body}", link_preview_options=preview)


async def _cmd_testcb(msg, parts, context, chat_id):
    await msg.reply_text(
        "🧪 Press the button to verify callback handling:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Tap me", callback_data="test")
        ]]),
    )


async def _cmd_ping(msg, parts, context, chat_id):
    uptime = int(time.time() - _start_time)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    parts_t = []
    if h:
        parts_t.append(f"{h}h")
    if m:
        parts_t.append(f"{m}m")
    parts_t.append(f"{s}s")
    await msg.reply_text(
        f"🏓 Pong!\n"
        f"Uptime: {' '.join(parts_t)}\n"
        f"Chats: {len(_known_chats)}\n"
        f"Cached users: {len(_user_names)}",
    )


async def _cmd_start(msg, parts, context, chat_id):
    if msg.chat.type == "private":
        text = (
            "👋 <b>Hi! I'm KkInstafix.</b>\n\n"
            "I fix social media links so they embed properly in Telegram.\n\n"
            "<b>In a group:</b> add me and I'll fix links automatically as they're posted.\n\n"
            "<b>Inline mode:</b> type <code>@KkInstaFixBot &lt;link&gt;</code> in any chat "
            "to get a fixed link without adding me.\n\n"
            "<b>Right here:</b> paste a link and I'll fix it.\n\n"
            "/help — all commands"
        )
    else:
        text = (
            "👋 <b>Welcome to Mehrab's link fixer bot.</b>\n\n"
            "Send me a link from Instagram, Twitter/X, TikTok, Reddit, "
            "Facebook, Threads, Bluesky, Pixiv, Tumblr, Bilibili, Snapchat, "
            "Spotify, Twitch, iFunny, FurAffinity, DeviantArt, or Dribbble and I'll "
            "rewrite it so Telegram shows a proper preview.\n\n"
            "If a preview looks wrong, tap <b>🔁 Embed not working?</b> under my "
            "message to try a different provider.\n\n"
            "<b>In a group:</b> add me and I'll fix links automatically.\n"
            "<b>Inline:</b> type <code>@KkInstaFixBot &lt;link&gt;</code> in any chat.\n\n"
            "/help — all commands"
        )
    await msg.reply_text(text, parse_mode="HTML")


async def _cmd_stats(msg, parts, context, chat_id):
    try:
        total, by_platform, by_sender = get_stats(chat_id)
        if total == 0:
            await msg.reply_text("No links fixed in this chat yet.")
            return
        lines = [f"📊 <b>Stats for this chat</b>", "", f"<b>{total}</b> links fixed total", ""]
        if by_platform:
            lines.append("<b>By platform</b>")
            for row in by_platform:
                emoji = PLATFORM_EMOJI.get(row["platform"], "")
                lines.append(f"  {emoji} {row['platform']} · {row['c']}")
            lines.append("")
        if by_sender:
            lines.append("<b>Top senders</b>")
            for row in by_sender:
                sid = row["sender_id"]
                name = _user_names.get(sid)
                if not name:
                    try:
                        member = await context.bot.get_chat_member(chat_id, sid)
                        name = member.user.first_name or member.user.username or f"User {sid}"
                        _user_names[sid] = name
                    except Exception:
                        name = f"User {sid}"
                lines.append(f"  {_html.escape(name)} · {row['c']}")
        await msg.reply_text("\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logger.exception("_cmd_stats failed in chat %s", chat_id)
        await msg.reply_text(f"⚠️ Stats error: {_html.escape(str(e))}", parse_mode="HTML")


async def _cmd_undo(msg, parts, context, chat_id):
    if not msg.reply_to_message:
        await msg.reply_text("Reply to one of my rewritten messages with /undo.")
        return
    original, sender = lookup_rewrite(chat_id, msg.reply_to_message.message_id)
    if not original:
        await msg.reply_text(
            "No record of that message — only rewrites from the last 7 days can be undone.\n"
            "Make sure you're replying directly to one of my rewritten messages."
        )
        return
    suffix = f" (from {_html.escape(sender)})" if sender else ""
    await msg.reply_text(
        f"Original link{suffix}:\n{original}",
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


async def _cmd_export(msg, parts, context, chat_id):
    try:
        data = export_chat_data(chat_id)
        payload = json.dumps(data, indent=2).encode("utf-8")
        buf = io.BytesIO(payload)
        buf.name = f"kkinstafix-chat-{chat_id}.json"
        await context.bot.send_document(
            chat_id=chat_id,
            document=buf,
            filename=buf.name,
            caption="Chat backup. Send this file back with caption /import to restore.",
        )
    except Exception:
        logger.exception("_cmd_export failed in chat %s", chat_id)
        await msg.reply_text("⚠️ Export failed — check the server logs.")


async def _cmd_import(msg, parts, context, chat_id):
    target = msg.reply_to_message if msg.reply_to_message else msg
    doc = target.document
    if not doc:
        await msg.reply_text(
            "Send a JSON backup as a document with caption /import, "
            "or reply to one with /import."
        )
        return
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        buf = bytearray()
        await tg_file.download_to_memory(buf)
        data = json.loads(bytes(buf).decode("utf-8"))
    except Exception as e:
        await msg.reply_text(f"Could not read file: {e}")
        return
    ok, info = import_chat_data(chat_id, data)
    await msg.reply_text(("✅ " if ok else "❌ ") + info)


async def _cmd_menu(msg, parts, context, chat_id):
    await msg.reply_text(
        "🛠 <b>Provider menu</b>\nTap a platform to change its provider. Current provider shown next to each name.",
        parse_mode="HTML",
        reply_markup=_build_platform_keyboard(chat_id),
    )


async def _cmd_enable(msg, parts, context, chat_id):
    update_chat_setting(chat_id, "enabled", 1)
    await msg.reply_text("Bot enabled in this chat.")


async def _cmd_disable(msg, parts, context, chat_id):
    update_chat_setting(chat_id, "enabled", 0)
    await msg.reply_text("Bot disabled in this chat. Use /enable to turn it back on.")


async def _cmd_listmuted(msg, parts, context, chat_id):
    muted = list(_muted_set(chat_id))
    if not muted:
        await msg.reply_text("No muted users in this chat.")
        return
    lines = [f"<b>Muted users ({len(muted)})</b>", ""]
    for uid in muted:
        try:
            member = await context.bot.get_chat_member(chat_id, uid)
            name = member.user.first_name or member.user.username or f"User {uid}"
            lines.append(f"• {_html.escape(name)} — <code>{uid}</code>")
        except Exception:
            lines.append(f"• <code>{uid}</code>")
    await msg.reply_text("\n".join(lines), parse_mode="HTML")


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
    custom = []
    for plat in sorted(PROVIDERS):
        cur = get_choice(chat_id, plat)
        default = PROVIDERS[plat]["default"]
        if cur != default:
            custom.append(f"  {plat}: {cur} → {default}")
    if not custom:
        await msg.reply_text("All providers are already at defaults.")
        return
    reset_providers(chat_id)
    lines = ["Providers reset to defaults.", ""] + custom
    await msg.reply_text("\n".join(lines))


async def _cmd_setprovider(msg, parts, context, chat_id):
    if len(parts) != 3:
        await msg.reply_text(
            "Usage: <code>/setprovider &lt;platform&gt; &lt;key&gt;</code>\n"
            "Example: <code>/setprovider instagram vx</code>\n\n"
            "Use /providers to see all platforms and available keys.",
            parse_mode="HTML",
        )
        return
    plat, prov = parts[1].lower(), parts[2].lower()
    if plat not in PROVIDERS:
        plats = ", ".join(sorted(PROVIDERS))
        await msg.reply_text(
            f"Unknown platform <b>{_html.escape(plat)}</b>.\n\nValid platforms: {plats}",
            parse_mode="HTML",
        )
        return
    if prov not in PROVIDERS[plat]["options"]:
        opts = ", ".join(PROVIDERS[plat]["options"])
        await msg.reply_text(
            f"Unknown provider <b>{_html.escape(prov)}</b> for {plat}.\n\nAvailable: {opts}",
            parse_mode="HTML",
        )
        return
    set_choice(chat_id, plat, prov)
    emoji = PLATFORM_EMOJI.get(plat, "")
    await msg.reply_text(f"{emoji} {plat} provider set to <b>{prov}</b>.", parse_mode="HTML")


async def _cmd_setsendermode(msg, parts, context, chat_id):
    modes = {
        "first_name": "first name (e.g. Mehrab)",
        "username": "@username",
        "full_name": "full name (e.g. Mehrab Khan)",
        "none": "no label — just the link",
    }
    if len(parts) != 2 or parts[1] not in modes:
        opts = "\n".join(f"  <code>{k}</code> — {v}" for k, v in modes.items())
        await msg.reply_text(
            f"Usage: <code>/setsendermode &lt;mode&gt;</code>\n\nModes:\n{opts}",
            parse_mode="HTML",
        )
        return
    update_chat_setting(chat_id, "sender_mode", parts[1])
    await msg.reply_text(
        f"Sender label set to: <b>{modes[parts[1]]}</b>", parse_mode="HTML"
    )


async def _cmd_setdedup(msg, parts, context, chat_id):
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.reply_text(
            "Usage: <code>/setdedup &lt;seconds&gt;</code>\n"
            "Example: <code>/setdedup 60</code> — same link won't appear twice within 60 seconds.",
            parse_mode="HTML",
        )
        return
    value = max(5, min(3600, int(parts[1])))
    update_chat_setting(chat_id, "dedup_window", value)
    minutes = value // 60
    human = f"{minutes} minute{'s' if minutes != 1 else ''}" if minutes else f"{value} seconds"
    await msg.reply_text(
        f"Dedup window set to <b>{value}s</b> — same link won't appear twice within {human}.",
        parse_mode="HTML",
    )


async def _cmd_testall(msg, parts, context, chat_id):
    if len(parts) < 2:
        await msg.reply_text(
            "Usage: <code>/testall &lt;platform&gt; [url]</code>\n"
            "Platforms: " + ", ".join(sorted(PROVIDERS)),
            parse_mode="HTML",
        )
        return
    platform = parts[1].lower()
    custom_url = parts[2] if len(parts) > 2 else None
    if platform not in PROVIDERS:
        await msg.reply_text(
            f"Unknown platform <b>{_html.escape(platform)}</b>.\n\nAvailable: " + ", ".join(sorted(PROVIDERS)),
            parse_mode="HTML",
        )
        return
    base_url = custom_url or SAMPLE_URLS.get(platform)
    if not base_url:
        await msg.reply_text(
            f"No sample URL for <b>{_html.escape(platform)}</b>. "
            f"Pass one: <code>/testall {_html.escape(platform)} https://...</code>",
            parse_mode="HTML",
        )
        return
    options = PROVIDERS[platform]["options"]
    emoji = PLATFORM_EMOJI.get(platform, "?")
    parsed = urlparse(base_url)
    status_msg = await msg.reply_text(
        f"Testing {len(options)} providers for {platform}..."
    )

    async def _test_one(key, host):
        # Use apply_provider so tracking is stripped, matching real bot behaviour.
        fixed = apply_provider(base_url, platform, key)
        preview = LinkPreviewOptions(
            is_disabled=False, url=fixed,
            prefer_large_media=True, show_above_text=False,
        )
        try:
            await msg.reply_text(
                f"{emoji} [{key}] {fixed}", link_preview_options=preview,
            )
        except Exception:
            logger.exception("/testall failed for %s %s in chat %s", platform, key, chat_id)
            await msg.reply_text(f"[{key}] failed")

    await asyncio.gather(*[_test_one(k, h) for k, h in options.items()])
    try:
        await status_msg.delete()
    except Exception:
        pass


async def _cmd_setratelimit(msg, parts, context, chat_id):
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.reply_text(
            "Usage: <code>/setratelimit &lt;count&gt; &lt;seconds&gt;</code>\n"
            "Example: <code>/setratelimit 5 30</code> — max 5 links per user per 30 seconds.",
            parse_mode="HTML",
        )
        return
    count = max(1, min(100, int(parts[1])))
    window = max(5, min(3600, int(parts[2])))
    update_chat_settings_batch(chat_id, {"rate_limit": count, "rate_window": window})
    await msg.reply_text(
        f"Rate limit set: <b>{count}</b> links per user per <b>{window}s</b>.",
        parse_mode="HTML",
    )


def _make_toggle_cmd(setting_key, on_text, off_text, usage):
    async def _cmd(msg, parts, context, chat_id):
        value = parse_on_off(parts[1]) if len(parts) == 2 else None
        if value is None:
            await msg.reply_text(usage, parse_mode="HTML")
            return
        update_chat_setting(chat_id, setting_key, value)
        await msg.reply_text(on_text if value else off_text)
    return _cmd


_cmd_ignoreforwards = _make_toggle_cmd(
    "ignore_forwards",
    "Forwarded posts will be ignored.",
    "Forwarded posts will now be processed too.",
    "Usage: <code>/ignoreforwards on|off</code>",
)

_cmd_fallback = _make_toggle_cmd(
    "provider_fallback",
    "Provider fallback enabled — if a provider is down, the next one is used.",
    "Provider fallback disabled — the chosen provider is always used.",
    "Usage: <code>/fallback on|off</code>",
)

_cmd_textspam = _make_toggle_cmd(
    "text_spam",
    "Repeated text deletion enabled.",
    "Repeated text deletion disabled.",
    "Usage: <code>/textspam on|off</code>",
)


async def _cmd_resetstats(msg, parts, context, chat_id):
    conn = db_connect()
    row = conn.execute(
        "SELECT COALESCE(SUM(count), 0) AS c FROM chat_stats WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    conn.execute("DELETE FROM chat_stats WHERE chat_id = ?", (chat_id,))
    conn.commit()
    await msg.reply_text(f"📊 Stats reset — cleared {row['c']} recorded link fixes.")


# ── Command dispatch maps ──────────────────────────────────────────────────────

PUBLIC_CMDS = {
    "/start": _cmd_start,
    "/testcb": _cmd_testcb,
    "/mehrab": _cmd_photo,
    "/mo": _cmd_photo,
    "/genius": _cmd_genius,
    "/about": _cmd_about,
    "/credits": _cmd_about,
    "/me": _cmd_about,
    "/providers": _cmd_providers,
    "/help": _cmd_help,
    "/status": _cmd_status,
    "/config": _cmd_status,
    "/stats": _cmd_stats,
    "/undo": _cmd_undo,
    "/clean": _cmd_clean,
    "/version": _cmd_version,
}

ADMIN_CMDS = {
    "/ping": _cmd_ping,
    "/menu": _cmd_menu,
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
    "/resetstats": _cmd_resetstats,
    "/testall": _cmd_testall,
    "/export": _cmd_export,
    "/import": _cmd_import,
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
    if msg.from_user and msg.from_user.first_name:
        _user_names[user_id] = msg.from_user.first_name
    chat_settings = get_chat_settings(chat_id)
    text = msg.text.strip()

    if is_user_muted(chat_id, user_id):
        await safe_delete(msg, "muted-user")
        return

    if chat_settings.get("ignore_forwards", 1) and is_forwarded(msg):
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
        # Plain text: only spam-dedup applies — no link rate budget consumed.
        if chat_settings.get("text_spam", 1) and len(text) >= 4:
            if seen_recent("text", chat_id, text.lower(), int(chat_settings["dedup_window"])):
                await safe_delete(msg, "duplicate-text")
        return

    rate_limit = int(chat_settings.get("rate_limit", RATE_LIMIT))
    rate_window = int(chat_settings.get("rate_window", RATE_WINDOW))
    if not check_rate(chat_id, user_id, rate_limit, rate_window):
        logger.info("Rate limited user %s in chat %s", user_id, chat_id)
        if not seen_recent("ratewarn", chat_id, str(user_id), rate_window):
            label = sender_label(msg.from_user, "first_name") or "you"
            try:
                await msg.reply_text(
                    f"⏱ Slow down, {_html.escape(label)} — rate limit hit.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await process_text(text, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else None
    sender_name = sender_label(msg.from_user, chat_settings["sender_mode"]) or ""
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    if fixed_count > 1:
        # Multiple links: preserve the full message context with all URLs replaced
        label = sender_label(msg.from_user, chat_settings["sender_mode"])
        post_text = f"{label}:\n{new_text}" if label else new_text
        post_parse_mode = None
    else:
        post_text = format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
        post_parse_mode = "HTML"

    # "Try another provider" button — single-link reposts where the platform
    # has more than one option to cycle through.
    markup = None
    if fixed_count == 1 and platform and len(PROVIDERS[platform]["options"]) > 1:
        options = list(PROVIDERS[platform]["options"])
        chosen_idx = options.index(get_choice(chat_id, platform))
        markup = _cycle_keyboard(platform, (chosen_idx + 1) % len(options))

    logger.info("Fixed %d link(s) in chat %s for user %s", fixed_count, chat_id, user_id)
    sent_msg = None
    deleted = await safe_delete(msg, "link-rewrite")
    if deleted:
        sent_msg = await safe_send_text(context, chat_id, post_text, preview=preview, reply_to=reply_to, parse_mode=post_parse_mode, reply_markup=markup)
        if not sent_msg:
            sent_msg = await safe_send_text(context, chat_id, post_text, reply_to=reply_to, parse_mode=post_parse_mode, reply_markup=markup)
    else:
        try:
            sent_msg = await msg.reply_text(post_text, link_preview_options=preview, parse_mode=post_parse_mode, reply_markup=markup)
            logger.info("Delete failed, replied instead in chat %s", chat_id)
        except Exception:
            logger.exception("reply_text fallback failed in chat %s", chat_id)

    for plat in fixed_platforms:
        increment_stat(chat_id, plat, user_id)
    if sent_msg and first_raw_url:
        store_rewrite(chat_id, sent_msg.message_id, first_raw_url, sender_name)

    # Background restriction check: if the embed provider returns a restriction
    # page, edit the message to explain why the preview looks broken.
    if sent_msg and first_preview_url and fixed_count == 1:
        asyncio.create_task(
            _warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, post_text, preview=preview, reply_markup=markup)
        )

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
    if chat_settings.get("ignore_forwards", 1) and is_forwarded(msg):
        return
    if not check_rate(chat_id, user_id, int(chat_settings.get("rate_limit", RATE_LIMIT)), int(chat_settings.get("rate_window", RATE_WINDOW))):
        return

    new_caption, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await process_text(msg.caption, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else msg.message_id
    clean_text = format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed caption link in chat %s for user %s", chat_id, user_id)
    try:
        sent_msg = await msg.reply_text(clean_text, link_preview_options=preview, reply_to_message_id=reply_to, parse_mode="HTML")
        for plat in fixed_platforms:
            increment_stat(chat_id, plat, user_id)
        if sent_msg and first_raw_url:
            store_rewrite(chat_id, sent_msg.message_id, first_raw_url,
                          sender_label(msg.from_user, chat_settings["sender_mode"]) or "")
        if sent_msg and first_preview_url and fixed_count == 1:
            asyncio.create_task(
                _warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, clean_text)
            )
    except Exception:
        logger.exception("Caption reply failed in chat %s", chat_id)

# ── Edit handler ──────────────────────────────────────────────────────────────
async def handle_edit(update, context):
    msg = update.edited_message
    if not msg or not msg.text:
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
        return
    if not check_rate(chat_id, user_id, int(chat_settings.get("rate_limit", RATE_LIMIT)), int(chat_settings.get("rate_window", RATE_WINDOW))):
        return
    if not URL_RE.search(msg.text):
        return

    new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await process_text(msg.text, chat_id, chat_settings)
    if not changed:
        return

    post_text = format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed edited link in chat %s for user %s", chat_id, user_id)
    try:
        sent_msg = await msg.reply_text(post_text, link_preview_options=preview, parse_mode="HTML")
        for plat in fixed_platforms:
            increment_stat(chat_id, plat, user_id)
        if sent_msg and first_raw_url:
            store_rewrite(chat_id, sent_msg.message_id, first_raw_url,
                          sender_label(msg.from_user, chat_settings["sender_mode"]) or "")
        if sent_msg and first_preview_url and fixed_count == 1:
            asyncio.create_task(
                _warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, post_text, preview=preview)
            )
    except Exception:
        logger.exception("Edit handler reply failed in chat %s", chat_id)

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

# ── Channel post handler ──────────────────────────────────────────────────────
async def handle_channel_post(update, context):
    msg = update.channel_post
    if not msg or not msg.text:
        return
    if is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    chat_settings = get_chat_settings(chat_id)
    if not chat_settings["enabled"]:
        return

    new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await process_text(msg.text, chat_id, chat_settings)
    if not changed:
        return

    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed link in channel %s", chat_id)
    try:
        sent = await context.bot.send_message(
            chat_id=chat_id,
            text=new_text,
            link_preview_options=preview,
            disable_notification=True,
        )
        for plat in fixed_platforms:
            increment_stat(chat_id, plat, 0)
        if sent and first_raw_url:
            store_rewrite(chat_id, sent.message_id, first_raw_url, "")
        if sent and first_preview_url and fixed_count == 1:
            asyncio.create_task(
                _warn_if_restricted(context, chat_id, sent.message_id, first_preview_url, new_text, preview=preview)
            )
    except Exception:
        logger.exception("Channel post reply failed in chat %s", chat_id)

# ── Document import handler ────────────────────────────────────────────────────
async def handle_import_document(update, context):
    msg = update.message
    if not msg or not msg.document or not msg.caption:
        return
    if not msg.caption.split()[0].lower().startswith("/import"):
        return
    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    if not await is_admin(context, chat_id, user_id, msg.chat.type):
        await msg.reply_text("Only admins can use /import.")
        return
    await _cmd_import(msg, msg.caption.split(), context, chat_id)


# ── Inline query handler ───────────────────────────────────────────────────────
async def handle_inline_query(update, context):
    query = update.inline_query
    if not query:
        return
    text = (query.query or "").strip()
    if not text:
        await query.answer([], cache_time=5, is_personal=True)
        return

    chat_settings = DEFAULT_CHAT_SETTINGS.copy()
    results = []
    urls = URL_RE.findall(text)
    for raw in urls[:5]:
        fixed, platform, original, preview = await fix_url(raw, 0, chat_settings)
        if fixed == raw:
            continue
        if platform:
            title = f"{PLATFORM_EMOJI.get(platform, '🔗')} Fix {platform} link"
        else:
            # Non-platform but changed: tracking stripped or short link expanded.
            # Show the destination domain so users can verify before sending.
            dest = urlparse(fixed).netloc.lower().removeprefix("www.") or fixed
            title = f"🧹 Clean link → {dest}"
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=title,
                description=fixed,
                input_message_content=InputTextMessageContent(
                    message_text=fixed,
                    link_preview_options=LinkPreviewOptions(
                        is_disabled=False, url=preview or fixed, prefer_large_media=True
                    ),
                ),
            )
        )

    if not results:
        if urls:
            hint_title = "All links already clean"
            hint_desc = "No tracking params to strip and no provider fix needed."
        else:
            hint_title = "No supported link found"
            hint_desc = "Paste an Instagram, Twitter, TikTok, Reddit, or other social media link."
        results.append(
            InlineQueryResultArticle(
                id=str(uuid.uuid4()),
                title=hint_title,
                description=hint_desc,
                input_message_content=InputTextMessageContent(
                    message_text="Tip: type @KkInstaFixBot followed by a social media link to get a fixed version."
                ),
            )
        )
    await query.answer(results, cache_time=10, is_personal=True)


async def _cycle_provider(cq, data, chat_id):
    # Answer immediately so the loading spinner clears regardless of what happens next.
    # (Telegram only allows one answer per callback query.)
    answered = False
    async def _answer(text="", alert=False):
        nonlocal answered
        if answered:
            return
        answered = True
        try:
            await cq.answer(text, show_alert=alert)
        except Exception as e:
            logger.warning("Cycle: cq.answer failed: %s", e)

    try:
        _, platform, idx_s = data.split(":")
        idx = int(idx_s)
    except Exception as e:
        await _answer(f"Bad callback data: {e}", alert=True)
        return

    if platform not in PROVIDERS:
        await _answer(f"Unknown platform: {platform}", alert=True)
        return

    options = list(PROVIDERS[platform]["options"])
    idx %= len(options)
    key = options[idx]
    logger.info("Cycle: chat=%s platform=%s -> key=%s (idx=%s)", chat_id, platform, key, idx)

    msg = cq.message
    if not hasattr(msg, "parse_entities"):
        await _answer("Message no longer accessible.", alert=True)
        return

    # Extract current URL directly from message entities — no DB needed.
    current_url = None
    display_text = None
    try:
        entity_texts = msg.parse_entities(types=["text_link", "url"])
        for entity, etext in entity_texts.items():
            if entity.type == "text_link":
                current_url = entity.url
                display_text = etext
                break
        if not current_url:
            for entity, etext in entity_texts.items():
                if entity.type == "url":
                    current_url = etext
                    break
        if not current_url:
            m = URL_RE.search(msg.text or "")
            current_url = m.group(0) if m else None
    except Exception as e:
        logger.exception("Cycle: entity extraction failed")
        await _answer(f"Entity error: {e}", alert=True)
        return

    logger.info("Cycle: url=%s display=%s", current_url, display_text)
    if not current_url:
        await _answer(f"No URL found in message (text={msg.text!r:.80})", alert=True)
        return

    # Swap host to the new provider, preserving path/query exactly.
    try:
        parsed = urlparse(current_url)
        new_host = PROVIDERS[platform]["options"][key]
        new_url = urlunparse((parsed.scheme, new_host, parsed.path, parsed.params, parsed.query, ""))
        noauth_embed = PROVIDERS[platform].get("noauth_embed", {})
        if key in noauth_embed:
            embed_host = PROVIDERS[platform]["options"][noauth_embed[key]]
            preview_url = urlunparse((parsed.scheme, embed_host, parsed.path, parsed.params, parsed.query, ""))
        else:
            preview_url = new_url

        emoji = PLATFORM_EMOJI.get(platform, "")
        safe_url = _html.escape(new_url, quote=True)
        if display_text:
            text = f'{emoji} <a href="{safe_url}">{_html.escape(display_text)}</a>'.strip()
        else:
            text = f"{emoji} {safe_url}".strip()
        preview = LinkPreviewOptions(
            is_disabled=False, url=preview_url, prefer_large_media=True, show_above_text=False
        )
        next_idx = (idx + 1) % len(options)
        await cq.edit_message_text(
            text,
            parse_mode="HTML",
            link_preview_options=preview,
            reply_markup=_cycle_keyboard(platform, next_idx),
        )
        logger.info("Cycle: edit OK %s/%s chat=%s", platform, key, chat_id)
        await _answer(f"Provider: {key}")
    except Exception as e:
        err = str(e).lower()
        if "not modified" in err or "message is not modified" in err:
            await _answer(f"Already on: {key}")
        else:
            logger.warning("Cycle edit failed for %s/%s: %s", platform, key, e)
            await _answer(f"Edit failed: {e}", alert=True)


# ── Callback query handler (inline menu) ───────────────────────────────────────
async def handle_callback(update, context):
    cq = update.callback_query
    if not cq or not cq.data:
        return
    data = cq.data
    try:
        chat_id = cq.message.chat_id
        user_id = cq.from_user.id if cq.from_user else 0
        chat_type = cq.message.chat.type
    except Exception as exc:
        logger.exception("handle_callback: failed to read message context for data=%s", data)
        try:
            await cq.answer(f"Context error: {exc}", show_alert=True)
        except Exception:
            pass
        return

    # "Try another provider" — available to everyone, it only re-targets the
    # embed of the bot's own message and is non-destructive.
    if data == "test":
        await cq.answer("✅ Callback works!", show_alert=True)
        return

    if data.startswith("e:"):
        await _cycle_provider(cq, data, chat_id)
        return

    if not await is_admin(context, chat_id, user_id, chat_type):
        await cq.answer("Admins only.", show_alert=True)
        return

    try:
        if data == "m:close":
            await cq.message.delete()
            await cq.answer()
            return
        if data == "m:back":
            await cq.edit_message_text(
                "🛠 <b>Provider menu</b>\nTap a platform to change its provider. Current provider shown next to each name.",
                parse_mode="HTML",
                reply_markup=_build_platform_keyboard(chat_id),
            )
            await cq.answer()
            return
        if data.startswith("m:p:"):
            platform = data[4:]
            if platform not in PROVIDERS:
                await cq.answer("Unknown platform.")
                return
            current = get_choice(chat_id, platform)
            host = PROVIDERS[platform]["options"].get(current, "")
            emoji = PLATFORM_EMOJI.get(platform, "")
            await cq.edit_message_text(
                f"{emoji} <b>{platform}</b>\nActive: <code>{current}</code> ({host})",
                parse_mode="HTML",
                reply_markup=_build_provider_keyboard(chat_id, platform),
            )
            await cq.answer()
            return
        if data.startswith("m:s:"):
            _, _, platform, key = data.split(":", 3)
            if platform not in PROVIDERS or key not in PROVIDERS[platform]["options"]:
                await cq.answer("Invalid choice.")
                return
            set_choice(chat_id, platform, key)
            host = PROVIDERS[platform]["options"].get(key, "")
            emoji = PLATFORM_EMOJI.get(platform, "")
            await cq.edit_message_text(
                f"{emoji} <b>{platform}</b>\nActive: <code>{key}</code> ({host})",
                parse_mode="HTML",
                reply_markup=_build_provider_keyboard(chat_id, platform),
            )
            await cq.answer(f"✅ {platform} → {key}")
            return
        await cq.answer("Unknown action.", show_alert=True)
    except Exception:
        logger.exception("Callback handling failed")
        await cq.answer("Something went wrong.", show_alert=True)


# ── Welcome handler ────────────────────────────────────────────────────────────
async def handle_new_members(update, context):
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    try:
        if any(member.id == context.bot.id for member in msg.new_chat_members):
            await msg.reply_text(WELCOME_TEXT, parse_mode="HTML")
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
    # Hide the "/" command menu so users aren't overwhelmed with options.
    # Commands still work when typed; Telegram just won't suggest them. The
    # "/" button persists if commands remain in ANY scope, so clear them all.
    for scope in (
        BotCommandScopeDefault(),
        BotCommandScopeAllPrivateChats(),
        BotCommandScopeAllGroupChats(),
        BotCommandScopeAllChatAdministrators(),
    ):
        try:
            await app.bot.delete_my_commands(scope=scope)
        except Exception:
            logger.warning("Failed clearing bot commands for scope %s",
                           type(scope).__name__, exc_info=True)
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
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE & filters.TEXT, handle_edit))
    app.add_handler(
        MessageHandler(
            (filters.PHOTO | filters.VIDEO | filters.Document.ALL) & filters.CaptionRegex(r"https?://"),
            handle_caption,
        )
    )
    app.add_handler(MessageHandler(filters.Sticker.ALL | filters.ANIMATION, handle_media))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/import"), handle_import_document))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST & filters.TEXT, handle_channel_post))
    app.add_handler(InlineQueryHandler(handle_inline_query))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.job_queue.run_repeating(periodic_cleanup, interval=3600, first=3600)
    _allowed = ["message", "edited_message", "callback_query", "inline_query", "channel_post"]
    if WEBHOOK_URL:
        wh_kwargs = dict(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=WEBHOOK_URL,
            drop_pending_updates=True,
            allowed_updates=_allowed,
        )
        if WEBHOOK_SECRET:
            wh_kwargs["secret_token"] = WEBHOOK_SECRET
        app.run_webhook(**wh_kwargs)
    else:
        app.run_polling(drop_pending_updates=True, allowed_updates=_allowed)


if __name__ == "__main__":
    main()
