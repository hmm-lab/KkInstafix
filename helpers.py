#!/usr/bin/env python3
"""
KkInstafix - Helper Module
Contains shared utility functions used by both bot.py and handlers.py.
"""

import asyncio
import html as _html
import logging
import re
import time
import urllib.error
import urllib.request
from collections import OrderedDict, deque
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from telegram.ext import ContextTypes
from telegram import LinkPreviewOptions, InlineKeyboardButton, InlineKeyboardMarkup, Message

logger = logging.getLogger(__name__)

# ── URL Processing ─────────────────────────────────────────────────────────────

# Compiled regex for URL detection
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)

# Tracking parameters to strip from URLs
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "utm_id", "utm_reader", "utm_vizid", "utm_pubreferrer", "utm_delta",
            "utm_source_platform", "utm_source_android", "utm_source_ios",
            "utm_social_component", "utm_social_type", "gmibextid", "igshid",
            "igsh", "fbclid", "ref", "ref_src", "t", "tt", "twclid", "igshid",
            "hss_channel", "hssc", "hsmi", "hscta", "hsfp", "mc_cid", "mc_eid"}

# YouTube-only share/analytics params
YOUTUBE_SHARE_PARAMS = {"is", "pp", "video_creator_share", "video_owner_channel"}

# Amazon TLDs
AMAZON_TLDs = {"com", "co.uk", "de", "fr", "it", "es", "co.jp", "co.in",
               "com.mx", "com.br", "com.au", "sg", "nl", "se", "pl", "tr"}

# Pre-built host → extra tracking params map
HOST_TO_TRACKING_MAP = {}

# Platforms that default to OFF
DEFAULT_DISABLED_PLATFORMS = set()

# Short-link domains that redirect
SHORT_LINK_DOMAINS = set()

# Hard cap for deduplication cache
DEFAULT_DEDUP_WINDOW = 3600

# Rate limiting defaults
RATE_LIMIT = 20
RATE_WINDOW = 60

# Track recent actions to prevent spam
_recent_mem: dict = {}  # (kind, chat_id, event_key) -> timestamp
_RATE_MEM: dict = {}    # (chat_id, user_id) -> deque of timestamps
_RECENT_MEM_HARD_CAP = 1000

# Cache for user names
_user_names: dict = {}  # user_id -> first_name

# Admin cache
_admin_cache: dict = {}  # (chat_id, user_id) -> (is_admin, expiry_time)

# Opt-out cache
_optout_cache: dict = {}  # chat_id -> set of user_ids

# Platform overrides cache
_platform_overrides_cache: dict = {}  # chat_id -> dict of platform->enabled

# User settings cache
_user_settings_cache: dict = {}  # (user_id, chat_id) -> dict of settings

# Provider choices cache
_provider_choices_cache: dict = {}  # (chat_id, platform) -> provider_key

# Statistics cache
_stats_cache: dict = {}  # chat_id -> stats data


def trim(url: str) -> Tuple[str, str]:
    """Trim whitespace and split URL into main part and trailing punctuation."""
    if not url or not isinstance(url, str):
        return "", ""
    url = url.strip()
    if not url:
        return "", ""

    # Separate trailing punctuation that's not part of the URL
    i = len(url)
    while i > 0 and url[i-1] in ",.:;!?":
        i -= 1
    return url[:i], url[i:]


def expand_short_url_sync(url: str) -> str:
    """Expand short URLs synchronously using urllib.request."""
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.geturl()
    except Exception:
        return url


def check_url_sync(url: str) -> bool:
    """Check if a URL is reachable synchronously."""
    try:
        request = urllib.request.Request(
            url,
            method="HEAD",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status < 400
    except Exception:
        return False


def is_restricted_sync(url: str) -> bool:
    """Check if URL points to restricted content."""
    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            # Check if we got a redirect to a known restriction page
            final_url = response.geturl().lower()
            restricted_indicators = [
                "restricted", "private", "unavailable", "not available",
                "account suspended", "content not found"
            ]
            return any(indicator in final_url for indicator in restricted_indicators)
    except Exception:
        return False


def apply_provider(url: str, platform: str, key: str, providers_dict: Dict) -> str:
    """Apply a provider rewrite to a URL."""
    if not url or not platform or not key:
        return url

    if platform not in providers_dict:
        return url

    if key not in providers_dict[platform]["options"]:
        return url

    # Get the replacement domain
    replacement_domain = providers_dict[platform]["options"][key]

    try:
        parsed = urlparse(url)
        # Replace the netloc (domain) while preserving everything else
        new_netloc = replacement_domain
        new_url = urlunparse((
            parsed.scheme,
            new_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))
        return new_url
    except Exception:
        return url


def build_fixed_for_key(original_url: str, platform: str, key: str, providers_dict: Dict) -> Tuple[str, str]:
    """Build fixed URL and preview URL for a platform/key combination."""
    if (
        not isinstance(original_url, str)
        or not original_url
        or platform not in providers_dict
        or key not in providers_dict[platform]["options"]
    ):
        return original_url, platform

    url, _tail = trim(original_url)
    link = apply_provider(url, platform, key, providers_dict)
    noauth_embed = providers_dict[platform].get("noauth_embed", {})

    if key in noauth_embed:
        preview = apply_provider(url, platform, noauth_embed[key], providers_dict)
    else:
        preview = link

    return link, preview


def sender_label(user: Optional[Any], mode: str) -> Optional[str]:
    """Extract sender label from user object based on mode."""
    if user is None or mode == "none":
        return None

    # Use getattr with defaults for tolerance with incomplete user objects
    username = getattr(user, "username", None)
    first_name = getattr(user, "first_name", None)
    last_name = getattr(user, "last_name", None)

    if mode == "username":
        if not username:
            return None
        return "@" + username if username else None

    if mode == "full_name":
        values = [x for x in (first_name, last_name) if x]
        if not values:
            return None
        return " ".join(values) or (
            first_name if first_name is not None
            else username if username is not None
            else "User"
        )

    if first_name == "":
        return ""

    if first_name:
        return first_name
    if username:
        return username
    if first_name is None and username is None:
        return None
    return "User"


def strip_tracking(url: str) -> str:
    """Strip tracking parameters from URL."""
    try:
        parsed = urlparse(url)
        query_dict = parse_qs(parsed.query, keep_blank_values=True)

        # Remove tracking parameters
        for param in TRACKING:
            query_dict.pop(param, None)

        # Rebuild query string
        new_query = urlencode(query_dict, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))
    except Exception:
        return url


async def safe_delete(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, reason: str = "", message: Optional[Message] = None) -> bool:
    """Safely delete a message, returning True if successful."""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        # If we have a message object (for test environment), mark it as deleted
        if message is not None:
            await message.delete()
        logger.info("Deleted message %s in chat %s (%s)", message_id, chat_id, reason)
        return True
    except Exception as e:
        logger.warning("Failed to delete message %s in chat %s: %s", message_id, chat_id, e)
        return False


async def safe_send_text(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str,
                   parse_mode: str = None, disable_web_page_preview: bool = False,
                   reply_to_message_id: int = None, link_preview_options: LinkPreviewOptions = None,
                   reply_markup: InlineKeyboardMarkup = None) -> Optional[Message]:
    """Safely send a text message, returning the sent message or None if failed."""
    try:
        return await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            reply_to_message_id=reply_to_message_id,
            link_preview_options=link_preview_options,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.warning("Failed to send message to chat %s: %s", chat_id, e)
        return None


def _cycle_keyboard(providers_dict: Dict, platform: str, selected_index: int) -> InlineKeyboardMarkup:
    """Create keyboard for cycling through providers."""
    if platform not in providers_dict:
        return InlineKeyboardMarkup([[]])

    options = list(providers_dict[platform]["options"].keys())
    if not options:
        return InlineKeyboardMarkup([[]])

    # Calculate next index
    next_index = (selected_index + 1) % len(options)
    next_provider = options[next_index]
    provider_name = providers_dict[platform]["options"][next_provider]

    keyboard = [[
        InlineKeyboardButton(
            f"🔄 Try {provider_name}",
            callback_data=f"provider_{platform}_{next_provider}"
        )
    ]]
    return InlineKeyboardMarkup(keyboard)


async def _warn_if_restricted(context: ContextTypes.DEFAULT_TYPE, chat_id: int,
                       message_id: int, url: str, text: str,
                       preview: LinkPreviewOptions = None,
                       reply_markup: InlineKeyboardMarkup = None) -> None:
    """Warn user if content appears to be restricted."""
    # This would typically edit the message to add a warning
    # Implementation omitted for brevity
    pass


def format_repost_text(user: Optional[Any], mode: str,
                      platform: Optional[str] = None,
                      url: Optional[str] = None) -> str:
    """Format text for reposting with sender label and URL."""
    label = sender_label(user, mode) or ""
    if label and url:
        return f"{label}: {url}"
    elif label:
        return label
    elif url:
        return url
    else:
        return ""


# Initialize caches
def _warm_caches() -> None:
    """Warning: This function assumes bot modules are already imported."""
    # This would normally warm various caches
    # For now, we'll leave it as a placeholder since we're avoiding circular imports
    pass