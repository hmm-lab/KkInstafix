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
    assert bot.get_platform("youtube.com", "/shorts/abc") == "youtube_watch"


def test_get_platform_subdomains():
    assert bot.get_platform("m.facebook.com", "/watch") == "facebook"
    assert bot.get_platform("old.reddit.com", "/r/test") == "reddit"
    assert bot.get_platform("clips.twitch.tv", "/test") == "twitch"


def test_get_platform_skips_fixer_hosts():
    assert bot.get_platform("kkclip.com", "/p/abc") is None
    assert bot.get_platform("vxtwitter.com", "/x/status/1") is None
    assert bot.get_platform("xcancel.com", "/user/status/1") is None
    assert bot.get_platform("redlib.org", "/r/test") is None
    assert bot.get_platform("proxitok.pabloferreiro.es", "/@u/video/1") is None


def test_get_platform_unknown():
    assert bot.get_platform("example.com", "/abc") is None


# ── apply_provider ────────────────────────────────────────────────────────────

def test_apply_provider_replaces_host():
    out = bot.apply_provider("https://instagram.com/p/abc", "instagram", "kkclip")
    assert "kkclip.com" in out
    assert "instagram.com" not in out
    assert "/p/abc" in out


def test_apply_provider_strips_tracking():
    out = bot.apply_provider("https://instagram.com/p/abc?igshid=1&utm_source=ig", "instagram", "kkclip")
    assert "igshid" not in out
    assert "utm_source" not in out


def test_apply_provider_strips_twitter_share_token():
    # ?s=20&t=<token> is Twitter's share tracking; both must be gone after rewrite.
    out = bot.apply_provider("https://twitter.com/u/status/1?s=20&t=AbCdToken", "twitter", "vx")
    assert out == "https://vxtwitter.com/u/status/1"


def test_apply_provider_strips_tiktok_session_junk():
    out = bot.apply_provider(
        "https://www.tiktok.com/@u/video/123?is_from_webapp=1&sender_device=pc&_t=xyz",
        "tiktok", "tnk",
    )
    assert out == "https://tnktok.com/@u/video/123"


def test_apply_provider_keeps_meaningful_query():
    # Non-tracking params on other platforms must survive (e.g. Reddit context).
    out = bot.apply_provider("https://www.reddit.com/r/x/comments/1/y?context=3", "reddit", "vx")
    assert "context=3" in out


def test_platform_tracking_keys_are_lowercase():
    for platform, keys in bot.PLATFORM_TRACKING.items():
        assert platform in bot.PROVIDERS, f"{platform} not a real platform"
        for k in keys:
            assert k == k.lower()


def test_cycle_button_url_also_strips_platform_tracking():
    # build_fixed_for_key powers the 🔁 button; it must clean share tokens too.
    link, preview = bot.build_fixed_for_key("https://twitter.com/u/status/1?t=tok", "twitter", "fx")
    assert "t=tok" not in link and "t=tok" not in preview


# ── INSTAGRAM_CONTENT_RE ──────────────────────────────────────────────────────

def test_instagram_content_re():
    assert bot.INSTAGRAM_CONTENT_RE.match("/p/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/reel/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/stories/highlights/abc")
    assert bot.INSTAGRAM_CONTENT_RE.match("/share/abc123")
    assert not bot.INSTAGRAM_CONTENT_RE.match("/profile/username")
    assert not bot.INSTAGRAM_CONTENT_RE.match("/explore/tags/cats")


# ── parse_on_off ──────────────────────────────────────────────────────────────

def test_parse_on_off():
    assert bot.parse_on_off("on") == 1
    assert bot.parse_on_off("yes") == 1
    assert bot.parse_on_off("1") == 1
    assert bot.parse_on_off("true") == 1
    assert bot.parse_on_off("off") == 0
    assert bot.parse_on_off("0") == 0
    assert bot.parse_on_off("false") == 0
    assert bot.parse_on_off("no") == 0
    assert bot.parse_on_off("maybe") is None
    assert bot.parse_on_off("") is None


# ── sender_label / format_repost_text ─────────────────────────────────────────

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


def test_format_repost_text_escapes_url_ampersand():
    # URL with query params: & must become &amp; for HTML parse mode.
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "first_name", platform="reddit",
                                 url="https://vxreddit.com/r/x/y?a=1&b=2")
    assert "&amp;b=2" in out
    assert "?a=1&b=2" not in out  # raw ampersand must not survive


def test_format_repost_text_escapes_url_quote():
    # A stray quote in the URL must not break out of the href attribute.
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "first_name", platform="twitter",
                                 url='https://vxtwitter.com/u/1"x')
    assert '"x">' not in out          # attribute not closed early
    assert "&quot;x" in out


def test_format_repost_text_none_mode_escapes_url():
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "none", platform="reddit",
                                 url="https://x/y?a=1&b=2")
    assert out == "https://x/y?a=1&amp;b=2"


def test_format_repost_text_none_mode():
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "none", platform="instagram", url="https://kkclip.com/p/x")
    assert out == "https://kkclip.com/p/x"


def test_format_repost_text_no_url():
    u = FakeUser(first_name="Mehrab")
    out = bot.format_repost_text(u, "first_name", platform="twitter", url=None)
    assert "🐦" in out
    assert "Mehrab" in out


# ── is_duplicate_update ───────────────────────────────────────────────────────

def test_is_duplicate_update_evicts_oldest():
    bot.SEEN_UPDATES.clear()
    bot.MAX_SEEN_UPDATES = 5
    for i in range(10):
        bot.is_duplicate_update(i)
    assert len(bot.SEEN_UPDATES) == 5
    assert 0 not in bot.SEEN_UPDATES
    assert 9 in bot.SEEN_UPDATES
    assert bot.is_duplicate_update(9) is True


# ── seen_recent (in-memory) ──────────────────────────────────────────────────

def test_seen_recent_window():
    bot._recent_mem.clear()
    assert bot.seen_recent("test", 1, "key1", 60) is False
    assert bot.seen_recent("test", 1, "key1", 60) is True
    assert bot.seen_recent("test", 1, "key2", 60) is False


def test_seen_recent_different_kinds():
    bot._recent_mem.clear()
    assert bot.seen_recent("fix", 1, "url", 60) is False
    assert bot.seen_recent("text", 1, "url", 60) is False


def test_seen_recent_hard_cap_clears_and_reinserts():
    bot._recent_mem.clear()
    cap = bot._RECENT_MEM_HARD_CAP
    # Fill the cache to just below the cap
    for i in range(cap):
        bot._recent_mem[("test", 0, f"k{i}")] = 0.0
    # One more call should trigger the clear and reinsert the new key
    result = bot.seen_recent("test", 1, "trigger", 60)
    assert result is False
    assert len(bot._recent_mem) == 1
    assert ("test", 1, "trigger") in bot._recent_mem


# ── check_rate (in-memory) ───────────────────────────────────────────────────

def test_check_rate_allows_up_to_limit():
    bot._rate_mem.clear()
    for _ in range(5):
        assert bot.check_rate(1, 1, 5, 60) is True
    assert bot.check_rate(1, 1, 5, 60) is False


def test_check_rate_different_users():
    bot._rate_mem.clear()
    for _ in range(5):
        bot.check_rate(1, 1, 5, 60)
    assert bot.check_rate(1, 1, 5, 60) is False
    assert bot.check_rate(1, 2, 5, 60) is True


def test_check_rate_different_chats():
    bot._rate_mem.clear()
    for _ in range(5):
        bot.check_rate(1, 1, 5, 60)
    assert bot.check_rate(1, 1, 5, 60) is False
    assert bot.check_rate(2, 1, 5, 60) is True


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


# ── build_fixed_for_key (provider-cycle button) ───────────────────────────────

def test_build_fixed_for_key_plain_provider():
    link, preview = bot.build_fixed_for_key(
        "https://twitter.com/x/status/1?utm_source=ig", "twitter", "fx"
    )
    assert link == preview                  # plain provider: link == preview
    assert "fxtwitter.com" in link
    assert "utm_source" not in link         # tracking stripped


def test_build_fixed_for_key_noauth_splits_link_and_preview():
    link, preview = bot.build_fixed_for_key(
        "https://twitter.com/x/status/1", "twitter", "xcancel"
    )
    assert "xcancel.com" in link            # clickable link → no-account frontend
    assert "vxtwitter.com" in preview       # preview → embed pair
    assert link != preview


def test_build_fixed_for_key_strips_trailing_tail():
    link, _ = bot.build_fixed_for_key("https://reddit.com/r/x/comments/1/y).", "reddit", "vx")
    assert link.endswith("/y")              # trailing ")." trimmed off
    assert "vxreddit.com" in link


def test_cycle_keyboard_encodes_platform_and_index():
    kb = bot._cycle_keyboard("tiktok", 3)
    btn = kb.inline_keyboard[0][0]
    assert btn.callback_data == "e:tiktok:3"


def test_platform_emoji_covers_all_platforms():
    for name in bot.PROVIDERS:
        assert name in bot.PLATFORM_EMOJI, f"{name} missing from PLATFORM_EMOJI"


# ── SHORT_LINK_DOMAINS ───────────────────────────────────────────────────────

def test_short_link_domains_are_lowercase():
    for d in bot.SHORT_LINK_DOMAINS:
        assert d == d.lower()


def test_short_link_domains_not_in_fixer_hosts():
    for d in bot.SHORT_LINK_DOMAINS:
        assert d not in bot.FIXER_HOSTS, f"short link domain {d} in FIXER_HOSTS would be skipped"


# ── providers_text / status_text ─────────────────────────────────────────────

def test_providers_text_contains_html():
    bot.init_db()
    text = bot.providers_text(99999)
    assert "<b>" in text
    for plat in bot.PROVIDERS:
        assert plat in text


def test_status_text_contains_html():
    bot.init_db()
    text = bot.status_text(99999)
    assert "<b>" in text
    assert "Bot is ON" in text or "Bot is OFF" in text


# ── export / import ──────────────────────────────────────────────────────────

def test_export_import_roundtrip():
    bot.init_db()
    cid = -100_999_888
    bot.update_chat_setting(cid, "dedup_window", 120)
    bot.set_choice(cid, "twitter", "fx")
    bot.mute_user(cid, 42)
    data = bot.export_chat_data(cid)
    assert data["version"] == 1
    assert data["settings"]["dedup_window"] == 120
    assert data["providers"]["twitter"] == "fx"
    assert 42 in data["muted_users"]
    # Import into a different chat
    cid2 = -100_999_777
    ok, msg = bot.import_chat_data(cid2, data)
    assert ok is True
    assert "imported" in msg
    assert str(cid) in msg  # mismatch warning
    assert bot.get_chat_settings(cid2)["dedup_window"] == 120
    assert bot.get_choice(cid2, "twitter") == "fx"
    assert bot.is_user_muted(cid2, 42)


def test_import_rejects_bad_format():
    bot.init_db()
    ok, msg = bot.import_chat_data(1, {"bad": True})
    assert ok is False
    assert "unsupported" in msg


# ── DEFAULT_CHAT_SETTINGS ────────────────────────────────────────────────────

def test_default_settings_keys_match_db():
    bot.init_db()
    s = bot.get_chat_settings(-100_111_222)
    for key in bot.DEFAULT_CHAT_SETTINGS:
        assert key in s, f"default key {key} not in returned settings"


def test_default_settings_include_all_toggles():
    for key in ("rate_limit", "rate_window", "ignore_forwards", "provider_fallback", "text_spam"):
        assert key in bot.DEFAULT_CHAT_SETTINGS


# ── New domains and short links ──────────────────────────────────────────────

def test_threads_com_detected():
    assert bot.get_platform("threads.com", "/@user/post/x") == "threads"
    assert bot.get_platform("www.threads.com", "/@user/post/x") == "threads"
    assert bot.get_platform("threads.net", "/@user/post/x") == "threads"


def test_b23_tv_is_short_link():
    assert "b23.tv" in bot.SHORT_LINK_DOMAINS


def test_toggle_commands_registered():
    for cmd in ("/setratelimit", "/ignoreforwards", "/fallback", "/textspam", "/resetstats"):
        assert cmd in bot.ADMIN_CMDS, f"{cmd} missing from ADMIN_CMDS"


# ── generic tracking strip (YouTube etc.) ─────────────────────────────────────

def test_strip_generic_tracking_removes_youtube_si():
    assert bot.strip_generic_tracking("https://youtu.be/abc?si=track") == "https://youtu.be/abc"


def test_strip_generic_tracking_keeps_real_params():
    out = bot.strip_generic_tracking("https://www.youtube.com/watch?v=abc&t=30&si=x")
    assert "v=abc" in out and "t=30" in out and "si=" not in out


def test_strip_generic_tracking_keeps_ambiguous_search_param():
    # "s" is in TRACKING but legit sites use it for search — generic stripper leaves it.
    assert "s=hello" in bot.strip_generic_tracking("https://blog.example.com/?s=hello")


def test_strip_generic_tracking_preserves_fragment():
    assert bot.strip_generic_tracking("https://example.com/p?utm_id=1#sec").endswith("#sec")


def test_taggay_fully_removed():
    for name in ("_cmd_taggay", "_cmd_untaggay", "_cmd_listgay", "tag_user", "is_user_tagged"):
        assert not hasattr(bot, name), f"{name} should be gone"
    for cmd in ("/taggay", "/untaggay", "/listgay"):
        assert cmd not in bot.ADMIN_CMDS and cmd not in bot.PUBLIC_CMDS


def test_clean_and_version_registered():
    assert "/clean" in bot.PUBLIC_CMDS
    assert "/version" in bot.PUBLIC_CMDS


def test_version_is_semver():
    import re
    assert re.match(r"^\d+\.\d+\.\d+$", bot.__version__)


def test_tiktok_t_share_is_short_path():
    # main expands vm/vt.tiktok.com via SHORT_LINK_DOMAINS; /t/ is path-based.
    import re
    assert re.match(r"^/t/", "/t/ZSabc/", re.IGNORECASE)


def test_youtu_be_not_network_expanded():
    # youtu.be is a pure path rewrite, never an HTTP redirect — expanding it
    # from a server IP can land on a Google CAPTCHA (google.com/sorry/...).
    assert "youtu.be" not in bot.SHORT_LINK_DOMAINS


def test_fix_url_youtu_be_path_rewrite_no_network():
    import asyncio
    bot.init_db()
    settings = bot.get_chat_settings(-100_808_002)

    async def fixed(u):
        return (await bot.fix_url(u, -100_808_002, settings))[0]

    # Real-world report: youtu.be/<id>?is=<token> must become a clean watch URL
    # without any network call (and never a google.com/sorry redirect).
    assert asyncio.run(fixed("https://youtu.be/SIYjCMpsDXI?is=oTJnkfU00tpjtqHG")) == \
        "https://www.youtube.com/watch?v=SIYjCMpsDXI"
    # ?si= variant too.
    assert asyncio.run(fixed("https://youtu.be/pIOGxOaST_s?si=track")) == \
        "https://www.youtube.com/watch?v=pIOGxOaST_s"
    # A timestamp is preserved.
    assert asyncio.run(fixed("https://youtu.be/abc123?t=42&si=x")) == \
        "https://www.youtube.com/watch?v=abc123&t=42"


def test_fix_url_youtu_be_returns_no_preview():
    import asyncio
    bot.init_db()
    settings = bot.get_chat_settings(-100_808_002)
    fixed, platform, original, preview = asyncio.run(
        bot.fix_url("https://youtu.be/SIYjCMpsDXI?is=tok", -100_808_002, settings)
    )
    # Plain link, no rich preview attached.
    assert platform is None
    assert preview is None


def test_instagram_share_path_triggers_expansion():
    import re
    assert re.match(r"^/share/", "/share/AbCdEf123/", re.IGNORECASE)
    assert not re.match(r"^/share/", "/p/AbCdEf123/", re.IGNORECASE)
    assert not re.match(r"^/share/", "/reel/AbCdEf123/", re.IGNORECASE)


def test_check_rate_uses_deque():
    from collections import deque
    bot._rate_mem.clear()
    bot.check_rate(99901, 99901, 5, 60)
    assert isinstance(bot._rate_mem.get((99901, 99901)), deque)


def test_get_platform_youtube_live_and_mobile():
    assert bot.get_platform("youtube.com", "/live/abcDEF") == "youtube_watch"
    assert bot.get_platform("m.youtube.com", "/shorts/abc") == "youtube_watch"
    assert bot.get_platform("m.youtube.com", "/live/abc") == "youtube_watch"
    # plain watch / profile paths are not rewritten (Telegram previews them fine)
    assert bot.get_platform("youtube.com", "/watch") is None
    assert bot.get_platform("youtube.com", "/@channel") is None


def test_youtube_path_re_matches_shorts_and_live():
    assert bot.YOUTUBE_PATH_RE.match("/shorts/abc123").group(1) == "abc123"
    assert bot.YOUTUBE_PATH_RE.match("/live/xyz_-9").group(1) == "xyz_-9"
    assert not bot.YOUTUBE_PATH_RE.match("/watch")


def test_fix_url_youtube_shorts_and_live_normalize():
    import asyncio
    bot.init_db()
    settings = bot.get_chat_settings(-100_808_001)

    async def fixed(u):
        return (await bot.fix_url(u, -100_808_001, settings))[0]

    assert asyncio.run(fixed("https://youtube.com/shorts/abc123?si=x")) == \
        "https://www.youtube.com/watch?v=abc123"
    assert asyncio.run(fixed("https://youtube.com/live/Lv2?t=120&feature=share")) == \
        "https://www.youtube.com/watch?v=Lv2&t=120"
    assert asyncio.run(fixed("https://m.youtube.com/shorts/Mob1?t=30")) == \
        "https://www.youtube.com/watch?v=Mob1&t=30"


def test_clean_url_platform_strips_share_tokens_keeps_host():
    # /clean must clean a platform link as thoroughly as a rewrite, minus the host swap.
    assert bot.clean_url("https://twitter.com/u/status/1?s=20&t=tok") == \
        "https://twitter.com/u/status/1"
    assert bot.clean_url("https://www.instagram.com/p/abc?igshid=1&utm_source=x") == \
        "https://www.instagram.com/p/abc"
    assert bot.clean_url("https://www.tiktok.com/@u/video/123?is_from_webapp=1&_t=z") == \
        "https://www.tiktok.com/@u/video/123"


def test_clean_url_generic_keeps_fragment_and_ambiguous_params():
    assert bot.clean_url("https://docs.example.com/g?utm_id=1#sec") == \
        "https://docs.example.com/g#sec"
    assert "s=hello" in bot.clean_url("https://blog.example.com/?s=hello")


def test_clean_url_keeps_meaningful_platform_params():
    assert "context=3" in bot.clean_url("https://www.reddit.com/r/x/comments/1/y?context=3")


def test_strip_youtube_is_share_param():
    # Real-world report: youtu.be share link used ?is= (not ?si=).
    assert bot.strip_generic_tracking(
        "https://youtu.be/pIOGxOaST_s?is=rUR1jaoJ8dqwR-EV"
    ) == "https://youtu.be/pIOGxOaST_s"


def test_strip_youtube_keeps_video_and_timestamp():
    out = bot.strip_generic_tracking("https://www.youtube.com/watch?v=abc&is=x&t=30")
    assert "v=abc" in out and "t=30" in out and "is=" not in out


def test_youtube_tracking_not_stripped_on_other_sites():
    # "is"/"pp" are too generic to strip globally — only on YouTube hosts.
    assert "is=loading" in bot.strip_generic_tracking("https://example.com/p?is=loading")
    assert "pp=1" in bot.strip_generic_tracking("https://shop.example.com/x?pp=1")


def test_process_text_no_substring_corruption():
    # When one URL token is a prefix of another, a naive str.replace would clobber
    # the longer link. process_text must rewrite each whole token exactly once.
    import asyncio
    bot.init_db()
    bot._recent_mem.clear()
    cid = -100_778_001
    settings = bot.get_chat_settings(cid)
    raw1 = "https://shop.example.com/p?utm_id=1"
    raw2 = "https://shop.example.com/p?utm_id=1&keep=12"  # raw1 is a string prefix
    text = f"x {raw1} y {raw2} z"
    new_text, changed, *_ = asyncio.run(bot.process_text(text, cid, settings))
    assert changed
    assert new_text == "x https://shop.example.com/p y https://shop.example.com/p?keep=12 z"
    assert "p&keep=12" not in new_text  # the substring-clobber signature


def test_process_text_multi_distinct_links():
    import asyncio
    bot.init_db()
    bot._recent_mem.clear()
    cid = -100_778_002
    settings = bot.get_chat_settings(cid)
    text = "a https://example.com/x?utm_source=z b https://other.example/y?fbclid=1 c"
    new_text, changed, _, _, _, count, _ = asyncio.run(bot.process_text(text, cid, settings))
    assert changed
    assert count == 2
    assert "utm_source" not in new_text and "fbclid" not in new_text
    assert "a " in new_text and " b " in new_text and " c" in new_text


def test_sample_urls_cover_all_platforms():
    # /testall and tools/check_providers.py silently skip any platform missing a
    # sample URL — this guard fails loudly if a new platform forgets one.
    missing = [p for p in bot.PROVIDERS if p not in bot.SAMPLE_URLS]
    assert not missing, f"platforms missing a SAMPLE_URL: {missing}"


def test_check_providers_tool_builds_url_for_every_host():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "tools", "check_providers.py")
    spec = importlib.util.spec_from_file_location("check_providers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    built = list(mod.build_check_urls())
    # one entry per provider host, each a valid http(s) URL pointing at the host
    assert len(built) == len(bot.FIXER_HOSTS)
    for platform, key, host, url, is_default in built:
        assert url.startswith("http")
        assert host in url
    # default flag is set for exactly one key per platform
    for platform in bot.PROVIDERS:
        defaults = [b for b in built if b[0] == platform and b[4]]
        assert len(defaults) == 1


def test_check_providers_is_up_classifier():
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "tools", "check_providers.py")
    spec = importlib.util.spec_from_file_location("check_providers", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_up(200) is True
    assert mod.is_up(404) is True   # host responded, post may be gone
    assert mod.is_up(500) is False
    assert mod.is_up(None) is False


def test_tco_in_short_link_domains():
    assert "t.co" in bot.SHORT_LINK_DOMAINS
    # Must not collide with any fixer host or platform, or expansion is skipped.
    assert "t.co" not in bot.FIXER_HOSTS
    assert bot.get_platform("t.co", "/abc123") is None


def test_strip_generic_tracking_removes_facebook_mibextid():
    out = bot.strip_generic_tracking("https://www.facebook.com/story?id=99&mibextid=abc")
    assert "mibextid" not in out
    assert "id=99" in out


def test_strip_generic_tracking_removes_new_campaign_params():
    for param in ("rdt", "ncid", "cmpid", "_branch_referrer", "oly_enc_id", "oly_anon_id", "extid"):
        url = f"https://example.com/article?{param}=track&real=keep"
        out = bot.strip_generic_tracking(url)
        assert f"{param}=" not in out, f"{param} survived in {out}"
        assert "real=keep" in out


def test_expand_cache_lru_evicts_oldest():
    from collections import OrderedDict
    bot._expand_cache.clear()
    original_max = bot._EXPAND_CACHE_MAX
    try:
        bot._EXPAND_CACHE_MAX = 3
        for i in range(4):
            url = f"https://youtu.be/vid{i}"
            bot._expand_cache[url] = f"https://www.youtube.com/watch?v=vid{i}"
            if len(bot._expand_cache) > bot._EXPAND_CACHE_MAX:
                bot._expand_cache.popitem(last=False)
        assert "https://youtu.be/vid0" not in bot._expand_cache
        assert "https://youtu.be/vid3" in bot._expand_cache
        assert len(bot._expand_cache) == 3
    finally:
        bot._EXPAND_CACHE_MAX = original_max
        bot._expand_cache.clear()
