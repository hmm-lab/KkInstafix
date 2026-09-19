"""
Provider configurations and related functions for KkInstafix.
"""

from typing import Dict, Any, Optional, List

# Platform emojis for display
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
    "kick": "🟢",
    "weibo": "🔴",
    "xiaohongshu": "📕",
    "linkedin": "💼",
    "pinterest": "📌",
}

# Provider configurations
PROVIDERS = {
    "instagram": {
        "default": "ee",
        "domains": ["instagram.com"],
        "options": {
            "kkclip": "kkclip.com",
            "kk": "kkinstagram.com",
            "ez": "instagramez.com",
            "vx": "vxinstagram.com",
            "ee": "eeinstagram.com",
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
            "ez": "twttrsz.com",
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
            "tfx": "tnfk.com",
            "ez": "tktokz.com",
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
            "libredd": "libredd.it",
        },
        "noauth_embed": {"redlib": "vx"},
    },
    "facebook": {
        "default": "ez",
        "domains": ["facebook.com", "fb.com", "fb.watch"],
        "options": {
            "ez": "facebookez.com",
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
    "piviv": {
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
    # Kick: clkick.com is the community fixer (kick.com -> clkick.com), covering
    # streams, clips and VODs. (Not EmbedEZ — EmbedEZ has no Kick support.)
    "kick": {
        "default": "cl",
        "domains": ["kick.com"],
        "options": {"cl": "clkick.com"},
    },
    # Weibo: weiboez.com is EmbedEZ's host but listed "Coming Soon" — so weibo is
    # in DEFAULT_DISABLED_PLATFORMS and ships OFF until an admin enables it.
    "weibo": {
        "default": "ez",
        "domains": ["weibo.com", "weibo.cn"],
        "options": {"ez": "weiboez.com"},
    },
    # Xiaohongshu (RED): the fixer is a community Cloudflare Worker that rewrites
    # the xhslink.com share-link host to xhslink.xky.us. It operates on the share
    # link itself, so we match xhslink.com (kept OUT of SHORT_LINK_DOMAINS so it
    # isn't expanded first) rather than xiaohongshu.com pages.
    "xiaohongshu": {
        "default": "xky",
        "domains": ["xhslink.com"],
        "options": {"xky": "xhslink.xky.us"},
    },

    "linkedin": {
        "default": "vx",
        "domains": ["linkedin.com"],
        "options": {
            "vx": "vxtdin.com",
            "ez": "lnkedin.ez",
        },
    },

    "pinterest": {
        "default": "vx",
        "domains": ["vxtin.com", "pin.ez"],
        "options": {
            "vx": "vxtin.com",
            "ez": "pin.ez",
        },
    },
}


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