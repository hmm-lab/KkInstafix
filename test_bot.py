"""Pure-function tests for bot.py — no Telegram API mocking required."""
import os
import sys

import pytest

# Avoid bot import crashing on missing token.
os.environ.setdefault("BOT_TOKEN", "test-token-not-used")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot  # noqa: E402


# ── strip_tracking ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,expected_has_param",
    [
        ("https://instagram.com/p/abc?igsh=xyz&utm_source=ig", False),
        ("https://twitter.com/x/status/1?fbclid=123", False),
        ("https://example.com/path?keep=this&utm_id=drop", True),
        ("https://example.com/path?keep=this", True),
    ],
)
def test_strip_tracking_removes_known_params(url, expected_has_param):
    stripped = bot.strip_tracking(url)
    for token in bot.TRACKING:
        assert token + "=" not in stripped, f"tracking token {token} survived in {stripped}"
    if expected_has_param:
        assert "keep=this" in stripped


def test_strip_tracking_preserves_path():
    assert "/p/abc" in bot.strip_tracking("https://instagram.com/p/abc?igshid=1")


# ── trim ──────────────────────────────────────────────────────────────────────

def test_trim_strips_trailing_punctuation():
    assert bot.trim("https://x.com/a).") == ("https://x.com/a", ").")
    assert bot.trim("https://x.com/a") == ("https://x.com/a", "")


# ── get_platform ──────────────────────────────────────────────────────────────

def test_get_platform_known():
    assert bot.get_platform("instagram.com", "/p/abc") == "instagram"
    assert bot.get_platform("www.instagram.com", "/reel/x") == "instagram"
    assert bot.get_platform("twitter.com", "/x/status/1") == "twitter"
    assert bot.get_platform("x.com", "/x/status/1") == "twitter"


def test_get_platform_subdomains():
    assert bot.get_platform("www.tiktok.com", "/@user/video/1") == "tiktok"
    assert bot.get_platform("m.reddit.com", "/r/x/comments/1") == "reddit"


def test_get_platform_skips_fixer_hosts():
    for host in bot.FIXER_HOSTS:
        assert bot.get_platform(host, "/anything") is None, f"fixer host {host} not skipped"


def test_get_platform_unknown():
    assert bot.get_platform("example.com", "/path") is None
    assert bot.get_platform("google.com", "/") is None


# ── apply_provider ────────────────────────────────────────────────────────────

def test_apply_provider_replaces_host():
    result = bot.apply_provider("https://twitter.com/user/status/1", "twitter", "vx")
    assert result.startswith("https://vxtwitter.com/")


def test_apply_provider_strips_tracking():
    result = bot.apply_provider(
        "https://instagram.com/p/abc?igsh=xyz", "instagram", "kkclip"
    )
    assert "igsh" not in result


# ── INSTAGRAM_CONTENT_RE ──────────────────────────────────────────────────────

def test_instagram_content_re():
    assert bot.INSTAGRAM_CONTENT_RE.match("/p/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/reel/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/stories/highlights/abc")
    assert not bot.INSTAGRAM_CONTENT_RE.match("/profile/username")
    assert not bot.INSTAGRAM_CONTENT_RE.match("/explore/tags/cats")


# ── parse_on_off ──────────────────────────────────────────────────────────────

def test_parse_on_off():
    assert bot.parse_on_off("on") == 1
    assert bot.parse_on_off("ON") == 1
    assert bot.parse_on_off("yes") == 1
    assert bot.parse_on_off("true") == 1
    assert bot.parse_on_off("1") == 1
    assert bot.parse_on_off("off") == 0
    assert bot.parse_on_off("OFF") == 0
    assert bot.parse_on_off("no") == 0
    assert bot.parse_on_off("false") == 0
    assert bot.parse_on_off("0") == 0
    assert bot.parse_on_off("maybe") is None
    assert bot.parse_on_off("") is None


# ── sender_label ──────────────────────────────────────────────────────────────

class _FakeUser:
    def __init__(self, first_name, last_name=None, username=None, id=1):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.id = id


def test_sender_label_modes():
    u = _FakeUser("Alice", "Smith", "alicesmith")
    assert bot.sender_label(u, "first_name") == "Alice"
    assert bot.sender_label(u, "username") == "@alicesmith"
    assert bot.sender_label(u, "full_name") == "Alice Smith"
    assert bot.sender_label(u, "none") is None


def test_sender_label_fallbacks():
    u = _FakeUser("Bob", username=None)
    assert bot.sender_label(u, "username") == "Bob"


# ── format_repost_text ────────────────────────────────────────────────────────

def test_format_repost_text_with_url():
    u = _FakeUser("Alice")
    text = bot.format_repost_text(u, "first_name", platform="twitter", url="https://vxtwitter.com/u/1")
    assert "Alice" in text
    assert "https://vxtwitter.com/u/1" in text


def test_format_repost_text_escapes_html():
    u = _FakeUser("<script>")
    text = bot.format_repost_text(u, "first_name", platform="instagram", url="https://kkclip.com/p/1")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text


def test_format_repost_text_none_mode():
    u = _FakeUser("Alice")
    text = bot.format_repost_text(u, "none", platform="twitter", url="https://vxtwitter.com/u/1")
    assert "https://vxtwitter.com/u/1" in text
    assert "Alice" not in text


def test_format_repost_text_no_url():
    u = _FakeUser("Alice")
    text = bot.format_repost_text(u, "first_name")
    assert "Alice" in text


# ── is_duplicate_update ───────────────────────────────────────────────────────

def test_is_duplicate_update_evicts_oldest():
    bot.SEEN_UPDATES.clear()
    for i in range(bot.MAX_SEEN_UPDATES + 5):
        bot.is_duplicate_update(i)
    assert len(bot.SEEN_UPDATES) == bot.MAX_SEEN_UPDATES


# ── seen_recent (DB-backed) ───────────────────────────────────────────────────

def test_seen_recent_db_window():
    bot.init_db()
    conn = bot.db_connect()
    conn.execute("DELETE FROM recent_events WHERE kind = 'test_window' AND chat_id = -1")
    conn.commit()
    assert bot.seen_recent("test_window", -1, "key1", 60) is False
    assert bot.seen_recent("test_window", -1, "key1", 60) is True
    assert bot.seen_recent("test_window", -1, "key2", 60) is False


def test_seen_recent_db_different_kinds():
    bot.init_db()
    conn = bot.db_connect()
    conn.execute("DELETE FROM recent_events WHERE chat_id = -2 AND event_key = 'url_kind_test'")
    conn.commit()
    assert bot.seen_recent("kind_a", -2, "url_kind_test", 60) is False
    assert bot.seen_recent("kind_b", -2, "url_kind_test", 60) is False


# ── check_rate (DB-backed) ────────────────────────────────────────────────────

def test_check_rate_db_enforces_limit():
    bot.init_db()
    # Use a unique chat/user pair to avoid cross-test interference
    conn = bot.db_connect()
    conn.execute("DELETE FROM rate_events WHERE chat_id = -999 AND user_id = 1")
    conn.commit()
    for _ in range(3):
        assert bot.check_rate(-999, 1, 3, 60) is True
    assert bot.check_rate(-999, 1, 3, 60) is False


# ── PROVIDERS config ──────────────────────────────────────────────────────────

def test_providers_all_have_default_and_options():
    for name, cfg in bot.PROVIDERS.items():
        assert cfg["default"] in cfg["options"], f"{name} default {cfg['default']} not in options"
        assert cfg["domains"], f"{name} has no domains"
        assert cfg["options"], f"{name} has no options"


def test_noauth_embed_keys_are_valid():
    for name, cfg in bot.PROVIDERS.items():
        noauth = cfg.get("noauth_embed", {})
        for noauth_key, embed_key in noauth.items():
            assert noauth_key in cfg["options"], f"{name} noauth key {noauth_key} not in options"
            assert embed_key in cfg["options"], f"{name} embed key {embed_key} not in options"
            assert embed_key not in noauth, f"{name} embed key {embed_key} is itself noauth"


def test_fixer_hosts_contains_all_provider_hosts():
    for cfg in bot.PROVIDERS.values():
        for host in cfg["options"].values():
            assert host in bot.FIXER_HOSTS


def test_platform_emoji_covers_all_platforms():
    for name in bot.PROVIDERS:
        assert name in bot.PLATFORM_EMOJI, f"{name} missing from PLATFORM_EMOJI"


# ── providers_text / status_text ─────────────────────────────────────────────

def test_providers_text_contains_platforms():
    bot.init_db()
    text = bot.providers_text(99999)
    for plat in bot.PROVIDERS:
        assert plat in text


def test_status_text_contains_settings():
    bot.init_db()
    text = bot.status_text(99999)
    assert "enabled" in text
    assert "rate_limit" in text


# ── DEFAULT_CHAT_SETTINGS ────────────────────────────────────────────────────

def test_default_settings_keys_match_db():
    bot.init_db()
    s = bot.get_chat_settings(-100_111_222)
    for key in bot.DEFAULT_CHAT_SETTINGS:
        assert key in s, f"default key {key} not in returned settings"


def test_default_settings_include_all_toggles():
    for key in ("rate_limit", "rate_window", "ignore_forwards", "provider_fallback", "text_spam"):
        assert key in bot.DEFAULT_CHAT_SETTINGS


# ── Admin commands registered ─────────────────────────────────────────────────

def test_admin_commands_registered():
    for cmd in ("/setratelimit", "/ignoreforwards", "/fallback", "/textspam",
                "/muteuser", "/unmuteuser", "/setprovider", "/resetproviders",
                "/setsendermode", "/setdedup", "/testall"):
        assert cmd in bot.ADMIN_CMDS, f"{cmd} missing from ADMIN_CMDS"


# ── dedup key strips tracking params ─────────────────────────────────────────

def test_strip_tracking_dedup_key_equivalence():
    u1 = "https://instagram.com/reel/abc/?igsh=foo"
    u2 = "https://instagram.com/reel/abc/?igsh=bar"
    assert bot.strip_tracking(u1) == bot.strip_tracking(u2)
