"""
Database operations for KkInstafix.
"""

import os
import sqlite3
import threading
from collections import OrderedDict
from typing import Dict, Any, Optional, Set, List, Tuple
from providers import PROVIDERS

# These will be imported from the main bot module or set up as needed
# For now, we'll define placeholders that will be replaced with actual imports
DB_FILE = os.path.join(os.environ.get("DATA_DIR", "."), "bot_data.sqlite3")

# Global connection and caches (these mirror the ones in bot.py)
_conn: sqlite3.Connection = None

# Cache dictionaries
_settings_cache: Dict[int, Dict[str, Any]] = {}      # chat_id -> settings dict
_providers_cache: Dict[int, Dict[str, str]] = {}     # chat_id -> {platform -> provider_key}
_muted_cache: Dict[int, Set[int]] = {}         # chat_id -> set of muted user_ids
_platform_override_cache: Dict[int, Dict[str, int]] = {}  # chat_id -> {platform: 1|0} explicit choices
_optout_cache: Dict[int, Set[int]] = {}        # chat_id -> set of user_ids who opted out of rewriting
_known_chats: Set[int] = set()
_file_id_cache: Dict[str, str] = {}       # filename -> telegram file_id
_admin_cache: Dict[Tuple[int, int], Tuple[bool, float]] = {}         # (chat_id, user_id) -> (is_admin, expiry_ts)
_user_names: Dict[int, str] = {}          # user_id -> first_name (from messages)
_recent_mem: Dict[Tuple[str, int, str], float] = {}       # (kind, chat_id, event_key) -> float timestamp
_RECENT_MEM_HARD_CAP = 200_000
_expand_cache: OrderedDict = OrderedDict()  # short URL -> expanded URL (LRU)
_expand_cache_lock = threading.Lock()
_EXPAND_CACHE_MAX = 2000
HEALTH_CACHE: Dict[str, Any] = {}
HEALTH_TTL = 600
SEEN_UPDATES: OrderedDict = OrderedDict()
MAX_SEEN_UPDATES = 2000
# User settings cache
_user_settings_cache: Dict[Tuple[int, int], Dict[str, Any]] = {}  # (user_id, chat_id) -> settings dict

# These constants mirror those in bot.py
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

_SETTING_INT_BOOL = frozenset({"enabled", "ignore_forwards", "provider_fallback", "text_spam"})
_SETTING_INT_BOUNDS = {
    "dedup_window": (5, 3600),
    "rate_limit": (1, 100),
    "rate_window": (5, 3600),
}
_SETTING_ENUMS = {
    "sender_mode": frozenset({"first_name", "username", "full_name", "none"}),
    "caption_style": frozenset({"reply"}),
}

# Import these from the main module when integrating
# from bot import PROVIDERS, logger


def db_connect() -> sqlite3.Connection:
    """Get or create the database connection."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
    return _conn


def _warm_chat_cache() -> None:
    """Load all chat settings into cache at startup."""
    conn = db_connect()
    for row in conn.execute("SELECT * FROM chat_settings").fetchall():
        cid = row["chat_id"]
        _known_chats.add(cid)
        _settings_cache[cid] = dict(row)
        # Import PROVIDERS from main module when integrating
        # _providers_cache[cid] = {p: cfg["default"] for p, cfg in PROVIDERS.items()}


def _warm_providers_cache() -> None:
    """Load provider settings into cache at startup."""
    conn = db_connect()
    for row in conn.execute("SELECT chat_id, platform, provider FROM provider_settings").fetchall():
        cid, plat, prov = row["chat_id"], row["platform"], row["provider"]
        if cid in _providers_cache and plat in PROVIDERS and prov in PROVIDERS[plat]["options"]:
            _providers_cache[cid][plat] = prov


def _warm_muted_cache() -> None:
    """Load muted users into cache at startup."""
    conn = db_connect()
    for row in conn.execute("SELECT chat_id, user_id FROM blocked_users").fetchall():
        _muted_cache.setdefault(row["chat_id"], set()).add(row["user_id"])


def _warm_platform_overrides_cache() -> None:
    """Load platform overrides into cache at startup."""
    conn = db_connect()
    for row in conn.execute("SELECT chat_id, platform, enabled FROM platform_overrides").fetchall():
        _platform_override_cache.setdefault(row["chat_id"], {})[row["platform"]] = row["enabled"]


def _warm_optout_cache() -> None:
    """Load opt-out users into cache at startup."""
    conn = db_connect()
    for row in conn.execute("SELECT chat_id, user_id FROM optout_users").fetchall():
        _optout_cache.setdefault(row["chat_id"], set()).add(row["user_id"])


def _warm_user_settings_cache() -> None:
    """Load user settings into cache at startup."""
    conn = db_connect()
    for row in conn.execute("SELECT user_id, chat_id, key, value FROM user_settings").fetchall():
        uid, cid, key, val = row["user_id"], row["chat_id"], row["key"], row["value"]
        _user_settings_cache.setdefault((uid, cid), {})[key] = val


def init_db() -> None:
    """Initialize the database schema and load caches."""
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

        CREATE TABLE IF NOT EXISTS disabled_platforms (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            PRIMARY KEY (chat_id, platform)
        );

        CREATE TABLE IF NOT EXISTS platform_overrides (
            chat_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            enabled INTEGER NOT NULL,
            PRIMARY KEY (chat_id, platform)
        );

        CREATE TABLE IF NOT EXISTS optout_users (
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

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            PRIMARY KEY (user_id, chat_id, key)
        );
        """
    )
    _migrate_chat_settings_columns(conn)
    # Migrate the old disabled_platforms table (v1.49–v1.51) into the newer
    # platform_overrides model as explicit "disabled" entries. Idempotent.
    conn.execute(
        "INSERT OR IGNORE INTO platform_overrides(chat_id, platform, enabled) "
        "SELECT chat_id, platform, 0 FROM disabled_platforms"
    )
    conn.commit()
    _warm_chat_cache()
    _warm_providers_cache()
    _warm_muted_cache()
    _warm_platform_overrides_cache()
    _warm_optout_cache()
    _warm_user_settings_cache()


# Canonical column DDL for chat_settings, mirroring the CREATE TABLE above.
_CHAT_SETTINGS_COLUMNS = [
    ("enabled", "INTEGER NOT NULL DEFAULT 1"),
    ("sender_mode", "TEXT NOT NULL DEFAULT 'first_name'"),
    ("dedup_window", "INTEGER NOT NULL DEFAULT 60"),
    ("rate_limit", "INTEGER NOT NULL DEFAULT 5"),
    ("rate_window", "INTEGER NOT NULL DEFAULT 30"),
    ("ignore_forwards", "INTEGER NOT NULL DEFAULT 1"),
    ("provider_fallback", "INTEGER NOT NULL DEFAULT 1"),
    ("caption_style", "TEXT NOT NULL DEFAULT 'reply'"),
    ("text_spam", "INTEGER NOT NULL DEFAULT 1"),
]


def _migrate_chat_settings_columns(conn: sqlite3.Connection) -> None:
    """Add any chat_settings column missing from an older database.

    An upgrade from a version that predates a setting (e.g. caption_style added
    in v1.37.0, text_spam earlier) leaves the existing table without that column.
    Without this, ensure_chat_settings' INSERT — which names every column —
    raises sqlite3.OperationalError on the first chat interaction.
    """
    existing = {r[1] for r in conn.execute("PRAGMA table_info(chat_settings)")}
    for name, ddl in _CHAT_SETTINGS_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE chat_settings ADD COLUMN {name} {ddl}")
            # Import logger when integrating
            # logger.info("Migrated chat_settings: added missing column %s", name)
    conn.commit()


def ensure_chat_settings(chat_id: int) -> None:
    """Ensure chat settings exist in database and cache."""
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
        # Import PROVIDERS when integrating
        # _providers_cache[chat_id] = {p: cfg["default"] for p, cfg in PROVIDERS.items()}
        pass


def get_chat_settings(chat_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
    """Get chat settings, using cache when possible, overridden by user-specific settings."""
    # Get base chat settings
    if chat_id in _settings_cache:
        settings = _settings_cache[chat_id].copy()
    else:
        ensure_chat_settings(chat_id)
        conn = db_connect()
        row = conn.execute("SELECT * FROM chat_settings WHERE chat_id = ?", (chat_id,)).fetchone()
        # Merge over defaults so a column missing from an older, un-migrated row
        # falls back to its default rather than producing an incomplete dict that
        # would KeyError on direct subscript in the handlers.
        settings = DEFAULT_CHAT_SETTINGS.copy()
        if row:
            settings.update({k: row[k] for k in row.keys()})
        _settings_cache[chat_id] = settings.copy()

    # Apply user-specific overrides if user_id is provided
    if user_id is not None:
        user_settings = get_user_settings(user_id, chat_id)
        settings.update(user_settings)

    return settings


def update_chat_setting(chat_id: int, key: str, value: Any) -> None:
    """Update a single chat setting.

    Args:
        chat_id: The Telegram chat ID
        key: The setting key to update
        value: The setting value to set

    Raises:
        ValueError: If the key is not a valid chat setting
        RuntimeError: If the database operation fails
    """
    # Validate that this is a known chat setting
    if key not in DEFAULT_CHAT_SETTINGS:
        raise ValueError(f"'{key}' is not a valid chat setting. Valid settings: {list(DEFAULT_CHAT_SETTINGS.keys())}")

    ensure_chat_settings(chat_id)
    conn = db_connect()
    try:
        conn.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
        conn.commit()
        if chat_id in _settings_cache:
            _settings_cache[chat_id][key] = value
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to update chat setting '{key}': {e}") from e


def update_chat_settings_batch(chat_id: int, updates: Dict[str, Any]) -> None:
    """Update multiple chat settings at once.

    Args:
        chat_id: The Telegram chat ID
        updates: Dictionary of setting keys and values to update

    Raises:
        ValueError: If any key is not a valid chat setting or if updates is not a dict
        RuntimeError: If the database operation fails
    """
    if not isinstance(updates, dict):
        raise ValueError("Updates must be a dictionary")

    # Validate all keys before making any changes
    invalid_keys = [key for key in updates.keys() if key not in DEFAULT_CHAT_SETTINGS]
    if invalid_keys:
        raise ValueError(f"Invalid chat settings: {invalid_keys}. Valid settings: {list(DEFAULT_CHAT_SETTINGS.keys())}")

    ensure_chat_settings(chat_id)
    conn = db_connect()
    try:
        for key, value in updates.items():
            conn.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
        conn.commit()
        if chat_id in _settings_cache:
            _settings_cache[chat_id].update(updates)
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to update chat settings: {e}") from e


def get_user_settings(user_id: int, chat_id: int) -> Dict[str, Any]:
    """Get user-specific settings for a user in a chat, using cache when possible.

    Args:
        user_id: The Telegram user ID
        chat_id: The Telegram chat ID

    Returns:
        Dictionary of user-specific settings. Empty dict if no settings found.

    Note:
        Returns a copy of the cached settings to prevent accidental mutation of cache.
    """
    cache_key = (user_id, chat_id)
    if cache_key in _user_settings_cache:
        return _user_settings_cache[cache_key].copy()
    conn = db_connect()
    rows = conn.execute(
        "SELECT key, value FROM user_settings WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id),
    ).fetchall()
    settings = {k: v for k, v in rows}
    _user_settings_cache[cache_key] = settings.copy()
    return settings


def set_user_setting(user_id: int, chat_id: int, key: str, value: Any) -> None:
    """Set a user-specific setting for a user in a chat.

    Args:
        user_id: The Telegram user ID
        chat_id: The Telegram chat ID
        key: The setting key to set
        value: The setting value (will be converted to string for storage)

    Raises:
        RuntimeError: If the database operation fails
        ValueError: If the key is empty or invalid
    """
    if not key or not isinstance(key, str):
        raise ValueError("Setting key must be a non-empty string")

    conn = db_connect()
    try:
        str_value = str(value)
        conn.execute(
            "INSERT OR REPLACE INTO user_settings(user_id, chat_id, key, value) VALUES(?, ?, ?, ?)",
            (user_id, chat_id, key, str_value),
        )
        conn.commit()
        _user_settings_cache[(user_id, chat_id)][key] = str_value
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to set user setting: {e}") from e


def update_user_settings_batch(user_id: int, chat_id: int, updates: Dict[str, Any]) -> None:
    """Update multiple user-specific settings at once.

    Args:
        user_id: The Telegram user ID
        chat_id: The Telegram chat ID
        updates: Dictionary of setting keys and values to update
                 (values will be converted to strings for storage)

    Raises:
        RuntimeError: If the database operation fails
        ValueError: If any key is empty or invalid, or if updates is not a dict
    """
    if not isinstance(updates, dict):
        raise ValueError("Updates must be a dictionary")

    # Validate all keys before making any changes
    for key in updates.keys():
        if not key or not isinstance(key, str):
            raise ValueError(f"Setting key must be a non-empty string, got: {key}")

    conn = db_connect()
    try:
        for key, value in updates.items():
            conn.execute(
                "INSERT OR REPLACE INTO user_settings(user_id, chat_id, key, value) VALUES(?, ?, ?, ?)",
                (user_id, chat_id, key, str(value)),
            )
        conn.commit()
        if (user_id, chat_id) in _user_settings_cache:
            _user_settings_cache[(user_id, chat_id)].update(updates)
    except Exception as e:
        conn.rollback()
        raise RuntimeError(f"Failed to update user settings: {e}") from e


def get_choice(chat_id: int, platform: str) -> str:
    """Get the provider choice for a chat/platform combination."""
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


def set_choice(chat_id: int, platform: str, provider: str) -> None:
    """Set the provider choice for a chat/platform combination."""
    conn = db_connect()
    conn.execute(
        "INSERT OR REPLACE INTO provider_settings(chat_id, platform, provider) VALUES(?, ?, ?)",
        (chat_id, platform, provider),
    )
    conn.commit()
    _providers_cache.setdefault(chat_id, {})[platform] = provider


def reset_providers(chat_id: int) -> None:
    """Reset provider settings for a chat to defaults."""
    conn = db_connect()
    conn.execute("DELETE FROM provider_settings WHERE chat_id = ?", (chat_id,))
    conn.commit()
    _providers_cache.pop(chat_id, None)


def _muted_set(chat_id: int) -> Set[int]:
    """Get the set of muted user IDs for a chat, loading from database if needed."""
    if chat_id not in _muted_cache:
        conn = db_connect()
        rows = conn.execute(
            "SELECT user_id FROM blocked_users WHERE chat_id = ?", (chat_id,)
        ).fetchall()
        _muted_cache[chat_id] = {r["user_id"] for r in rows}
    return _muted_cache[chat_id]


def mute_user(chat_id: int, user_id: int) -> None:
    """Mute a user in a chat."""
    conn = db_connect()
    conn.execute(
        "INSERT OR IGNORE INTO blocked_users(chat_id, user_id) VALUES(?, ?)",
        (chat_id, user_id),
    )
    conn.commit()
    _muted_set(chat_id).add(user_id)


def unmute_user(chat_id: int, user_id: int) -> None:
    """Unmute a user in a chat."""
    conn = db_connect()
    conn.execute(
        "DELETE FROM blocked_users WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    )
    conn.commit()
    _muted_set(chat_id).discard(user_id)


def is_user_muted(chat_id: int, user_id: int) -> bool:
    """Check if a user is muted in a chat."""
    return user_id in _muted_set(chat_id)