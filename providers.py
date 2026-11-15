"""
Provider configurations and related functions for KkInstafix.
"""

from typing import Dict, Any, Optional, List

# Platform emojis for display
PLATFORM_EMOJI = {
    "youtube": "▶️",
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
    "kick": "🟢",
    "weibo": "🔴",
    "xiaohongshu": "📕",
    "linkedin": "💼",
    "pinterest": "📌",
}

# Provider configurations. See cloudflare/PROVIDER_REVIEW.md for refresh evidence.
PROVIDER_REVISION = "2026-11-15"
PROVIDERS = {'youtube': {'default': 'native', 'domains': ['youtube.com', 'youtu.be', 'koutu.be'],
                         'options': {'native': 'www.youtube.com', 'koutube': 'koutube.com'}},
 'instagram': {'default': 'ee',
               'domains': ['instagram.com', 'kkclip.com', 'kkinstagram.com', 'instagram7.com'],
               'options': {'vx': 'vxinstagram.com',
                           'ee': 'eeinstagram.com',
                           'uu': 'uuinstagram.com',
                           'zz': 'zzinstagram.com',
                           'to': 'toinstagram.com',
                           'embeds': 'ig.embeds.now',
                           'revived': 'fkinstagram.com',
                           'ins': 'ins.so'}},
 'twitter': {'default': 'vx',
             'domains': ['twitter.com', 'x.com'],
             'options': {'vx': 'vxtwitter.com',
                         'fx': 'fxtwitter.com',
                         'fixvx': 'fixvx.com',
                         'fixupx': 'fixupx.com',
                         'ez': 'xeezz.com',
                         'twittpr': 'twittpr.com',
                         'xcancel': 'xcancel.com'},
             'noauth_embed': {'xcancel': 'vx'}},
 'tiktok': {'default': 'tnk',
            'domains': ['tiktok.com'],
            'options': {'tnk': 'tnktok.com',
                        'ez': 'tiktokez.com',
                        'kk': 'kktiktok.com',
                        'fix': 'fixtiktok.com'}},
 'reddit': {'default': 'vx',
            'domains': ['reddit.com'],
            'options': {'vx': 'vxreddit.com',
                        'rx': 'rxddit.com',
                        'rxy': 'rxyddit.com',
                        'ez': 'redditez.com',
                        'redlib': 'redlib.org'},
            'noauth_embed': {'redlib': 'vx'}},
 'facebook': {'default': 'bed',
              'domains': ['facebook.com', 'fb.com', 'fb.watch'],
              'options': {'bed': 'facebed.seria.moe'}},
 'threads': {'default': 'fix',
             'domains': ['threads.net', 'threads.com'],
             'options': {'fix': 'fixthreads.seria.moe', 'vx': 'vxthreads.net'}},
 'bluesky': {'default': 'bskx',
             'domains': ['bsky.app'],
             'options': {'bskx': 'bskx.app',
                         'bsyy': 'bsyy.app',
                         'bskye': 'bskye.app',
                         'xbsky': 'xbsky.app',
                         'fx': 'fxbsky.app',
                         'vx': 'vxbsky.app',
                         'boobsky': 'boobsky.app'}},
 'piviv': {'default': 'ph',
           'domains': ['pixiv.net'],
           'options': {'ph': 'phixiv.net', 'pp': 'ppxiv.net'}},
 'tumblr': {'default': 'tp',
            'domains': ['tumblr.com'],
            'options': {'tp': 'tpmblr.com', 'txt': 'txtumblr.com'}},
 'bilibili': {'default': 'vx',
              'domains': ['bilibili.com', 'b23.tv'],
              'options': {'vx': 'vxbilibili.com',
                          'fx': 'fxbilibili.seria.moe',
                          'ez': 'bilibiliez.com'}},
 'snapchat': {'default': 'ez', 'domains': ['snapchat.com'], 'options': {'ez': 'snapchatez.com'}},
 'spotify': {'default': 'fx', 'domains': ['open.spotify.com'], 'options': {'fx': 'fxspotify.com'}},
 'twitch': {'default': 'fx',
            'domains': ['twitch.tv', 'clips.twitch.tv'],
            'options': {'fx': 'fxtwitch.seria.moe'}},
 'ifunny': {'default': 'ez', 'domains': ['ifunny.co'], 'options': {'ez': 'ifunnyez.co'}},
 'furaffinity': {'default': 'xfa',
                 'domains': ['furaffinity.net'],
                 'options': {'xfa': 'xfuraffinity.net', 'fxr': 'fxraffinity.net'}},
 'deviantart': {'default': 'fix',
                'domains': ['deviantart.com'],
                'options': {'fix': 'fixdeviantart.com', 'fx': 'fxdeviantart.com'}},
 'dribbble': {'default': 'tv', 'domains': ['dribbble.com'], 'options': {'tv': 'dribbbletv.com'}},
 'kick': {'default': 'cl', 'domains': ['kick.com'], 'options': {'cl': 'clkick.com'}},
 'weibo': {'default': 'ez', 'domains': ['weibo.com', 'weibo.cn'], 'options': {'ez': 'weiboez.com'}},
 'xiaohongshu': {'default': 'xky',
                 'domains': ['xhslink.com'],
                 'options': {'xky': 'xhslink.xky.us'}},
 'pinterest': {'default': 'ez', 'domains': ['pinterest.com'], 'options': {'ez': 'pinterestez.com'}}}


def get_provider_domain(platform: str, provider_key: str) -> Optional[str]:
    """
    Get the domain for a specific platform and provider key.

    Args:
        platform: The platform name (e.g., 'twitter', 'tiktok')
        provider_key: The provider key (e.g., 'ez', 'vx')

    Returns:
        The provider domain string or None if not found
    """
    if platform in PROVIDERS and provider_key in PROVIDERS[platform]["options"]:
        return PROVIDERS[platform]["options"][provider_key]
    return None


def get_default_provider(platform: str) -> Optional[str]:
    """
    Get the default provider key for a platform.

    Args:
        platform: The platform name

    Returns:
        The default provider key or None if platform not found
    """
    if platform in PROVIDERS:
        return PROVIDERS[platform]["default"]
    return None


def is_valid_provider(platform: str, provider_key: str) -> bool:
    """
    Check if a provider key is valid for a given platform.

    Args:
        platform: The platform name
        provider_key: The provider key to check

    Returns:
        True if valid, False otherwise
    """
    return (
        platform in PROVIDERS
        and provider_key in PROVIDERS[platform]["options"]
    )


def get_provider_options(platform: str) -> Dict[str, str]:
    """
    Get all provider options for a platform.

    Args:
        platform: The platform name

    Returns:
        Dictionary mapping provider keys to domains
    """
    if platform in PROVIDERS:
        return PROVIDERS[platform]["options"].copy()
    return {}


def get_provider_domains(platform: str) -> Dict[str, str]:
    """
    Get all provider domains for a platform (alias for get_provider_options).

    Args:
        platform: The platform name

    Returns:
        Dictionary mapping provider keys to domains
    """
    return get_provider_options(platform)


def get_platforms() -> List[str]:
    """
    Get list of all supported platforms.

    Returns:
        List of platform names
    """
    return list(PROVIDERS.keys())


def get_platform_domains(platform: str) -> List[str]:
    """
    Get list of domains associated with a platform.

    Args:
        platform: The platform name

    Returns:
        List of domain strings
    """
    if platform in PROVIDERS:
        return PROVIDERS[platform]["domains"].copy()
    return []


def get_noauth_embed_map(platform: str) -> Dict[str, str]:
    """
    Get the noauth_embed mapping for a platform.

    Args:
        platform: The platform name

    Returns:
        Dictionary mapping provider keys to embed domains for no-auth previews
    """
    if platform in PROVIDERS:
        return PROVIDERS[platform].get("noauth_embed", {}).copy()
    return {}