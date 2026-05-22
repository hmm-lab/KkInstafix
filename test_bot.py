"""Pure-function tests for bot.py — no Telegram API mocking required."""
import os
import sys

import pytest

# Avoid bot import crashing on missing token.
os.environ.setdefault("BOT_TOKEN", "test-token-not-used")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bot  # noqa: E402


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


def test_trim_strips_trailing_punctuation():
    assert bot.trim("https://x.com/a).") == ("https://x.com/a", ").")
    assert bot.trim("https://x.com/a") == ("https://x.com/a", "")


def test_get_platform_known():
    assert bot.get_platform("instagram.com", "/p/abc") == "instagram"
    assert bot.get_platform("www.instagram.com", "/reel/x") == "instagram"
    assert bot.get_platform("twitter.com", "/x/status/1") == "twitter"
    assert bot.get_platform("x.com", "/x/status/1") == "twitter"
    assert bot.get_platform("youtube.com", "/shorts/abc") == "youtube_shorts"


def test_get_platform_skips_fixer_hosts():
    assert bot.get_platform("kkclip.com", "/p/abc") is None
    assert bot.get_platform("vxtwitter.com", "/x/status/1") is None


def test_get_platform_unknown():
    assert bot.get_platform("example.com", "/abc") is None


def test_apply_provider_replaces_host():
    out = bot.apply_provider("https://instagram.com/p/abc", "instagram", "kkclip")
    assert "kkclip.com" in out
    assert "instagram.com" not in out
    assert "/p/abc" in out


def test_instagram_content_re():
    assert bot.INSTAGRAM_CONTENT_RE.match("/p/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/reel/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/stories/highlights/abc")
    assert not bot.INSTAGRAM_CONTENT_RE.match("/profile/username")
    assert not bot.INSTAGRAM_CONTENT_RE.match("/explore/tags/cats")


def test_parse_on_off():
    assert bot.parse_on_off("on") == 1
    assert bot.parse_on_off("yes") == 1
    assert bot.parse_on_off("1") == 1
    assert bot.parse_on_off("off") == 0
    assert bot.parse_on_off("0") == 0
    assert bot.parse_on_off("maybe") is None


class FakeUser:
    def __init__(self, first_name=None, last_name=None, username=None):
        self.first_name = first_name
        self.last_name = last_name
        self.username = username


def test_sender_label_modes():
    u = FakeUser(first_name="Mehrab", last_name="Khan", username="mehrabx")
    assert bot.sender_label(u, "first_name") == "Mehrab"
    assert bot.sender_label(u, "username") == "@mehrabx"
    assert bot.sender_label(u, "full_name") == "Mehrab Khan"
    assert bot.sender_label(u, "none") is None
    assert bot.sender_label(None, "first_name") is None


def test_sender_label_fallbacks():
    u = FakeUser(first_name=None, last_name=None, username="onlyuser")
    assert bot.sender_label(u, "first_name") == "onlyuser"
    u2 = FakeUser(first_name=None, last_name=None, username=None)
    assert bot.sender_label(u2, "first_name") == "User"


def test_format_repost_text_with_url():
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "first_name", platform="instagram", url="https://kkclip.com/p/x")
    assert "📷" in out
    assert "Mehrab" in out
    assert 'href="https://kkclip.com/p/x"' in out


def test_format_repost_text_escapes_html():
    u = FakeUser(first_name="<script>evil</script>")
    out = bot.format_repost_text(u, "first_name", platform="instagram", url="https://kkclip.com/p/x")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_format_repost_text_none_mode():
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "none", platform="instagram", url="https://kkclip.com/p/x")
    assert out == "https://kkclip.com/p/x"


def test_is_duplicate_update_evicts_oldest():
    bot.SEEN_UPDATES.clear()
    bot.MAX_SEEN_UPDATES = 5
    for i in range(10):
        bot.is_duplicate_update(i)
    assert len(bot.SEEN_UPDATES) == 5
    # Oldest should have been evicted
    assert 0 not in bot.SEEN_UPDATES
    # Newer should be present
    assert 9 in bot.SEEN_UPDATES
    # Re-seeing the same id returns True
    assert bot.is_duplicate_update(9) is True


def test_providers_all_have_default_and_options():
    for name, cfg in bot.PROVIDERS.items():
        assert cfg["default"] in cfg["options"], f"{name} default {cfg['default']} not in options"
        assert cfg["domains"], f"{name} has no domains"
        assert cfg["options"], f"{name} has no options"
