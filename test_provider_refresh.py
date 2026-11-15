"""Provider catalogue consistency and semantic health checks."""
import importlib.util
from pathlib import Path
import providers

spec=importlib.util.spec_from_file_location('provider_checker',Path(__file__).parent/'tools/check_providers.py')
checker=importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

def test_provider_catalogue_has_current_supported_domains():
    p=providers.PROVIDERS
    assert p['instagram']['default']=='ee'
    assert p['tiktok']['options']['ez']=='tiktokez.com'
    assert p['twitter']['options']['ez']=='xeezz.com'
    assert p['facebook']['options']['bed']=='facebed.seria.moe'
    assert p['threads']['options']['fix']=='fixthreads.seria.moe'
    assert p['pinterest']['options']['ez']=='pinterestez.com'
    assert 'linkedin' not in p
    assert not {'ez', 'kkclip', 'kk'} & p['instagram']['options'].keys()

def test_error_card_and_login_are_not_healthy_embeds():
    assert not checker.has_usable_embed('<meta property="og:title" content="Log in or sign up"><meta property="og:image" content="logo.png">')
    assert not checker.has_usable_embed('<meta property="og:title" content="Oops, something went wrong"><meta property="og:image" content="error.png">')
    assert not checker.has_usable_embed('<html>og: error string only</html>')

def test_text_only_posts_and_direct_media_are_valid_embeds():
    assert checker.has_usable_embed('<meta property="og:title" content="jack"><meta property="og:description" content="just setting up my twttr">')
    assert checker.has_usable_embed('', 'video/mp4')


def test_instagram_dlrf_share_token_removed_from_original_and_provider_links():
    from bot import clean_url, apply_provider
    for host in ("www.instagram.com", "eeinstagram.com"):
        raw = f"https://{host}/reel/example/?dlrf=secret&psln=secret&img_index=2"
        assert clean_url(raw) == f"https://{host}/reel/example/?img_index=2"
    assert apply_provider("https://instagram.com/reel/example/?dlrf=secret", "instagram", "ee") == "https://eeinstagram.com/reel/example/"


def test_instagram_dynamic_tokens_removed_but_functional_queries_kept():
    from bot import clean_url, apply_provider
    for host in ("www.instagram.com", "eeinstagram.com"):
        raw = f"https://{host}/reel/example/?xtok=secret&vrfl=secret&unknown_share_token=secret&img_index=2"
        assert clean_url(raw) == f"https://{host}/reel/example/?img_index=2"
        assert apply_provider(raw, "instagram", "ee") == "https://eeinstagram.com/reel/example/?img_index=2"
    assert clean_url("https://example.com/reel/a?xtok=needed") == "https://example.com/reel/a?xtok=needed"


def test_gist_review_additions_keep_native_youtube_and_verified_bluesky_options():
    p = providers.PROVIDERS
    assert p["youtube"]["default"] == "native"
    assert p["youtube"]["options"]["koutube"] == "koutube.com"
    assert p["bluesky"]["options"]["boobsky"] == "boobsky.app"
    assert p["bluesky"]["options"]["vx"] == "vxbsky.app"
    assert p["instagram"]["default"] == "ee"


def test_kyrela_instagram_candidates_and_username_paths():
    from bot import clean_url, apply_provider, INSTAGRAM_CONTENT_RE
    for key, host in [("to", "toinstagram.com"), ("embeds", "ig.embeds.now"), ("revived", "fkinstagram.com"), ("ins", "ins.so")]:
        assert providers.PROVIDERS["instagram"]["options"][key] == host
        raw = "https://instagram.com/author/reel/abc/?new_token=secret&img_index=2"
        assert clean_url(raw) == "https://instagram.com/author/reel/abc/?img_index=2"
        assert apply_provider(raw, "instagram", key) == f"https://{host}/author/reel/abc/?img_index=2"
        assert INSTAGRAM_CONTENT_RE.match("/author/reel/abc/")


def test_shared_tracking_rules_cover_supported_platforms_and_keep_functional_parameters():
    from bot import clean_url, apply_provider
    assert clean_url("https://youtube.com/watch?v=abc&t=30&list=PL1&gclid=secret&utm_new=secret&ab_channel=secret") == "https://youtube.com/watch?v=abc&t=30&list=PL1"
    assert apply_provider("https://twitter.com/a/status/1?gclid=secret&utm_new=secret", "twitter", "vx") == "https://vxtwitter.com/a/status/1"
    assert clean_url("https://example.com/a?keep=needed&utm_future=secret") == "https://example.com/a?keep=needed"


def test_provider_hosts_use_original_platform_specific_cleanup_rules():
    from bot import clean_url, apply_provider
    assert clean_url("https://pinterestez.com/pin/1?rs=secret&amp=secret&keep=needed") == "https://pinterestez.com/pin/1?keep=needed"
    assert apply_provider("https://pinterest.com/pin/1?rs=secret&amp=secret&keep=needed", "pinterest", "ez") == "https://pinterestez.com/pin/1?keep=needed"


def test_furtrack_verified_photo_paths_and_profiles():
    from bot import get_platform, apply_provider
    assert get_platform("www.furtrack.com", "/p/826598") == "furtrack"
    assert get_platform("furtrack.com", "/user/Aero") is None
    assert apply_provider("https://furtrack.com/p/826598?utm_source=secret", "furtrack", "fix") == "https://furtrack.owo.lgbt/p/826598"
