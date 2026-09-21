#!/usr/bin/env python3
"""
KkInstafix - Handler Module
Contains all Telegram event handlers for link rewriting functionality.
"""

import asyncio
import html as _html
import logging
import time
from typing import Any, Optional, Set, Dict, List, Tuple, Callable, Awaitable

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    LinkPreviewOptions,
    Message,
    Update,
)
from telegram.constants import ChatAction
from telegram.error import Conflict, TimedOut
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, InlineQueryHandler

# Import from local modules
import database
import helpers

logger = logging.getLogger(__name__)

# Command handler maps (moved from bot.py for cleaner separation)
PUBLIC_CMDS: Dict[str, Callable] = {}
ADMIN_CMDS: Dict[str, Callable] = {}


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages for link rewriting."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.message
    if not msg or not msg.text:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if bot.is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    if msg.from_user and msg.from_user.first_name:
        bot._user_names[user_id] = msg.from_user.first_name
    chat_settings = database.get_chat_settings(chat_id, user_id)
    text = msg.text.strip()

    if bot.is_user_muted(chat_id, user_id):
        await helpers.safe_delete(context, chat_id, msg.message_id, "muted-user", message=msg)
        return

    if chat_settings.get("ignore_forwards", 1) and bot.is_forwarded(msg):
        return

    if text.startswith("/"):
        parts = text.split()
        cmd = parts[0].split("@")[0].lower()

        # Import bot inside function to avoid circular imports
        import bot

        if cmd in bot.PUBLIC_CMDS:
            await bot.PUBLIC_CMDS[cmd](msg, parts, context, chat_id)
            return

        if cmd in bot.ADMIN_CMDS:
            if not await bot.is_admin(context, chat_id, user_id, msg.chat.type):
                await msg.reply_text("Only admins can use that command.")
                return
            await bot.ADMIN_CMDS[cmd](msg, parts, context, chat_id)
            return

        # Unknown command
        await msg.reply_text(
            "Unknown command. Available commands: /help, /platform, /clean, /preview, /optout, /optin, /version"
        )
        return

    if not chat_settings["enabled"]:
        return

    has_url = bool(helpers.URL_RE.search(text))

    if not has_url:
        # Plain text: only spam-dedup applies — no link rate budget consumed.
        if chat_settings.get("text_spam", 1) and len(text) >= 4:
            if bot.seen_recent("text", chat_id, text.lower(), int(chat_settings["dedup_window"])):
                await helpers.safe_delete(context, chat_id, msg.message_id, "duplicate-text", message=msg)
        return

    if bot.is_user_optout(chat_id, user_id):
        return   # user asked not to have their links rewritten in this chat

    rate_limit = int(chat_settings.get("rate_limit", bot.RATE_LIMIT))
    rate_window = int(chat_settings.get("rate_window", bot.RATE_WINDOW))
    if not bot.check_rate(chat_id, user_id, rate_limit, rate_window):
        logger.info("Rate limited user %s in chat %s", user_id, chat_id)
        if not bot.seen_recent("ratewarn", chat_id, str(user_id), rate_window):
            label = helpers.sender_label(msg.from_user, "first_name") or "you"
            try:
                await msg.reply_text(
                    f"⏱ Slow down, {_html.escape(label)} — rate limit hit.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    # Import bot inside function to avoid circular imports
    import bot
    new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await bot.process_text(text, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else None
    sender_name = helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or ""
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    if fixed_count > 1:
        # Multiple links: preserve the full message context with all URLs replaced
        label = helpers.sender_label(msg.from_user, chat_settings["sender_mode"])
        post_text = f"{label}:\n{new_text}" if label else new_text
        post_parse_mode = None
    else:
        post_text = helpers.format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
        post_parse_mode = "HTML"

    # "Try another provider" button — single-link reposts where the platform
    # has more than one option to cycle through.
    markup = None
    if fixed_count == 1 and platform and len(bot.PROVIDERS[platform]["options"]) > 1:
        options = list(bot.PROVIDERS[platform]["options"].keys())
        chosen_idx = options.index(database.get_choice(chat_id, platform))
        markup = helpers._cycle_keyboard(bot.PROVIDERS, platform, (chosen_idx + 1) % len(options))

    logger.info("Fixed %d link(s) in chat %s for user %s", fixed_count, chat_id, user_id)
    sent_msg = None
    deleted = await helpers.safe_delete(context, chat_id, msg.message_id, "link-rewrite", message=msg)
    if deleted:
        # Try multiple fallback strategies for sending the message
        sent_msg = await helpers.safe_send_text(context, chat_id, post_text, link_preview_options=preview, reply_to_message_id=reply_to, parse_mode=post_parse_mode, reply_markup=markup)
        if not sent_msg:
            logger.info("First send attempt failed, trying without link preview options")
            sent_msg = await helpers.safe_send_text(context, chat_id, post_text, reply_to_message_id=reply_to, parse_mode=post_parse_mode, reply_markup=markup)
        if not sent_msg:
            logger.info("Second send attempt failed, trying without parse mode and reply markup")
            sent_msg = await helpers.safe_send_text(context, chat_id, post_text, reply_to_message_id=reply_to)
        if not sent_msg:
            logger.info("Third send attempt failed, trying with minimal parameters")
            # Truncate text if too long (Telegram limit is 4096 characters)
            truncated_text = post_text[:4096] if len(post_text) > 4096 else post_text
            sent_msg = await helpers.safe_send_text(context, chat_id, truncated_text)
        if not sent_msg:
            logger.info("All send attempts failed, showing cleaned original URL")
            # Fallback: show cleaned original URL with sender label and provider shuffle button
            cleaned_url = helpers.strip_tracking(first_raw_url) if first_raw_url else ""
            label = helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or ""
            if label and cleaned_url:
                fallback_text = f"{label}: {cleaned_url}"
            elif label:
                fallback_text = label
            elif cleaned_url:
                fallback_text = cleaned_url
            else:
                fallback_text = "Link fixing failed"
            await helpers.safe_send_text(context, chat_id, fallback_text, reply_to_message_id=reply_to, reply_markup=markup, parse_mode=fallback_parse_mode)
    else:
        try:
            sent_msg = await msg.reply_text(post_text, link_preview_options=preview, parse_mode=post_parse_mode, reply_markup=markup)
            logger.info("Delete failed, replied instead in chat %s", chat_id)
        except Exception:
            logger.exception("reply_text fallback failed in chat %s", chat_id)

    if sent_msg:
        for plat in fixed_platforms:
            bot.increment_stat(chat_id, plat, user_id)
        if first_raw_url:
            bot.store_rewrite(chat_id, sent_msg.message_id, first_raw_url, sender_name)

    # Background restriction check: if the embed provider returns a restriction
    # page, edit the message to explain why the preview looks broken.
    if sent_msg and first_preview_url and fixed_count == 1:
        asyncio.create_task(
            helpers._warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, post_text, preview=preview, reply_markup=markup)
        )


async def handle_caption(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming message captions for link rewriting."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.message
    if not msg or not msg.caption:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if bot.is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    chat_settings = database.get_chat_settings(chat_id, user_id)

    if not chat_settings["enabled"]:
        return
    if bot.is_user_muted(chat_id, user_id):
        await helpers.safe_delete(context, chat_id, msg.message_id, "muted-user-caption", message=msg)
        return
    if chat_settings.get("ignore_forwards", 1) and bot.is_forwarded(msg):
        return
    if bot.is_user_optout(chat_id, user_id):
        return   # user opted out of link rewriting
    if not bot.check_rate(chat_id, user_id, int(chat_settings.get("rate_limit", bot.RATE_LIMIT)), int(chat_settings.get("rate_window", bot.RATE_WINDOW))):
        return

    # Import bot inside function to avoid circular imports
    import bot
    new_caption, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await bot.process_text(msg.caption, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.reply_to_message.message_id if msg.reply_to_message else msg.message_id
    clean_text = helpers.format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
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
            bot.increment_stat(chat_id, plat, user_id)
        if sent_msg and first_raw_url:
            bot.store_rewrite(chat_id, sent_msg.message_id, first_raw_url,
                              helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or "")
        if sent_msg and first_preview_url and fixed_count == 1:
            asyncio.create_task(
                helpers._warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, clean_text)
            )
    except Exception:
        logger.exception("Caption reply failed in chat %s")


async def handle_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edited messages for link rewriting."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.edited_message
    if not msg or not msg.text:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if bot.is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    chat_settings = database.get_chat_settings(chat_id, user_id)

    if not chat_settings["enabled"]:
        return
    if chat_settings.get("ignore_forwards", 1) and bot.is_forwarded(msg):
        return
    if bot.is_user_muted(chat_id, user_id):
        return
    if bot.is_user_optout(chat_id, user_id):
        return   # user opted out of link rewriting
    if not bot.check_rate(chat_id, user_id, int(chat_settings.get("rate_limit", bot.RATE_LIMIT)), int(chat_settings.get("rate_window", bot.RATE_WINDOW))):
        return

    # Import bot inside function to avoid circular orbits
    import bot
    new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await bot.process_text(msg.text, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.message_id
    sender_name = helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or ""
    preview = LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    if fixed_count > 1:
        # Multiple links: preserve the full message context with all URLs replaced
        label = helpers.sender_label(msg.from_user, chat_settings["sender_mode"])
        post_text = f"{label}:\n{new_text}" if label else new_text
        post_parse_mode = None
    else:
        post_text = helpers.format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url)
        post_parse_mode = "HTML"

    # "Try another provider" button — single-link reposts where the platform
    # has more than one option to cycle through.
    markup = None
    if fixed_count == 1 and platform and len(bot.PROVIDERS[platform]["options"]) > 1:
        options = list(bot.PROVIDERS[platform]["options"].keys())
        chosen_idx = options.index(database.get_choice(chat_id, platform))
        markup = helpers._cycle_keyboard(bot.PROVIDERS, platform, (chosen_idx + 1) % len(options))

    logger.info("Fixed edited message link in chat %s for user %s", chat_id, user_id)
    try:
        sent_msg = await msg.reply_text(post_text, link_preview_options=preview, parse_mode=post_parse_mode, reply_markup=markup)
        for plat in fixed_platforms:
            bot.increment_stat(chat_id, plat, user_id)
        if sent_msg and first_raw_url:
            bot.store_rewrite(chat_id, sent_msg.message_id, first_raw_url,
                              helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or "")
        if sent_msg and first_preview_url and fixed_count == 1:
            asyncio.create_task(
                helpers._warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, post_text)
            )
    except Exception:
        logger.exception("Failed to send reply for edited message in chat %s")


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document uploads for settings import/export."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.message
    if not msg or not msg.document:
        return
    if msg.from_user and msg.from_user.is_bot:
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0

    # Only process in private chats for security
    if msg.chat.type != "private":
        await msg.reply_text("Settings import/export only works in private chats.")
        return

    # Check if user is admin
    if not await bot.is_admin(context, chat_id, user_id, msg.chat.type):
        await msg.reply_text("Only admins can import/export settings.")
        return

    # Download the document
    try:
        doc_file = await msg.document.get_file()
        doc_bytes = await doc_file.download_as_bytearray()
        doc_str = doc_bytes.decode('utf-8')
    except Exception as e:
        logger.exception("Failed to download document: %s", e)
        await msg.reply_text("Failed to download the document.")
        return

    # Import the settings
    try:
        success, message = bot.import_chat_data(doc_str)
        if success:
            await msg.reply_text(f"✅ Settings imported successfully!\n{message}")
        else:
            await msg.reply_text(f"❌ Failed to import settings:\n{message}")
    except Exception as e:
        logger.exception("Failed to import chat data: %s", e)
        await msg.reply_text(f"❌ Error importing settings: {str(e)}")


async def handle_import_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle document imports via caption starting with /import."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.message
    if not msg or not msg.document or not msg.caption:
        return
    _cap_parts = msg.caption.split()
    if not _cap_parts or not _cap_parts[0].lower().startswith("/import"):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    if not await bot.is_admin(context, chat_id, user_id, msg.chat.type):
        await msg.reply_text("Only admins can use /import.")
        return
    await bot._cmd_import(msg, msg.caption.split(), context, chat_id)


async def handle_inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline queries for link preview."""
    # Import bot inside function to avoid circular imports
    import bot
    query = update.inline_query
    if not query or not query.query:
        return

    # Only process if there's a URL in the query
    if not helpers.URL_RE.search(query.query):
        # Return hint about usage
        results = [
            InlineQueryResultArticle(
                id="hint",
                title="No supported link",
                description="The provided text doesn't contain a supported link",
                input_message_content=InputTextMessageContent(
                    "🔗 Share links like: https://twitter.com/user/status/123\n"
                    "✨ Get fixed versions for cleaner previews!"
                )
            )
        ]
        await query.answer(results, cache_time=10, is_personal=True)
        return

    text = query.query.strip()
    # Process the text to get fixed URL
    try:
        new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await bot.process_text(
            text, 0, {"enabled": True, "dedup_window": 60}  # Use dummy chat ID and settings for inline queries
        )
    except Exception as e:
        logger.exception("Error processing inline query: %s", e)
        await query.answer([
            InlineQueryResultArticle(
                id="error",
                title="Error processing link",
                description="Could not process the provided URL",
                input_message_content=InputTextMessageContent("❌ Error processing link")
            )
        ], cache_time=1, is_personal=True)
        return


    # Handle cases where URL was found but no fixing is needed
    # We know a URL was present because URL_RE.search(query.query) was True above
    if not changed or first_raw_url == first_fixed_url:
        # URL found but no changes needed (already clean)
        results = [
            InlineQueryResultArticle(
                id="alreadyclean",
                title="Already clean",
                description="The link is already clean and doesn't need fixing",
                input_message_content=InputTextMessageContent(text)
            )
        ]
        await query.answer(results, cache_time=10, is_personal=True)
        return

    # Create result with fixed URL
    # Determine if we changed the domain (platform fix) or just cleaned parameters
    from urllib.parse import urlparse
    try:
        raw_parsed = urlparse(first_raw_url)
        fixed_parsed = urlparse(first_fixed_url)
        domain_changed = (raw_parsed.netloc != fixed_parsed.netloc) or (raw_parsed.scheme != fixed_parsed.scheme)
    except Exception:
        domain_changed = bool(platform)  # fallback to original logic

    if domain_changed:
        title = f"Fixed {platform} link" if platform else "Fixed link"
    else:
        title = "Clean link"

    description = first_fixed_url
    if first_preview_url and first_preview_url != first_fixed_url:
        description += f" (preview: {first_preview_url})"

    results = [
        InlineQueryResultArticle(
            id="fixed",
            title=title,
            description=description,
            input_message_content=InputTextMessageContent(
                first_fixed_url,
                disable_web_page_preview=False
            ),
            thumbnail_url="https://img.icons8.com/color/48/000000/link--v1.png"
        )
    ]

    # Also provide the original if it was changed
    if changed and first_raw_url != first_fixed_url:
        results.append(
            InlineQueryResultArticle(
                id="original",
                title="Original link",
                description=first_raw_url,
                input_message_content=InputTextMessageContent(first_raw_url),
                thumbnail_url="https://img.icons8.com/color/48/000000/link--v2.png"
            )
        )

    await query.answer(results, cache_time=30, is_personal=True)


async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback queries from inline menus."""
    # Import bot inside function to avoid circular imports
    import bot
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    data = query.data
    if not data.startswith("provider_"):
        return

    try:
        _, platform, provider_key = data.split("_", 2)
    except ValueError:
        await query.edit_message_text("❌ Invalid provider selection")
        return

    chat_id = query.message.chat_id if query.message else 0
    user_id = query.from_user.id if query.from_user else 0

    # Check if user is admin
    if not await bot.is_admin(context, chat_id, user_id, query.message.chat.type if query.message else "private"):
        await query.edit_message_text("❌ Only admins can change provider settings")
        return

    # Validate platform and provider
    if platform not in bot.PROVIDERS:
        await query.edit_message_text(f"❌ Unknown platform: {platform}")
        return

    if provider_key not in bot.PROVIDERS[platform]["options"]:
        await query.edit_message_text(f"❌ Invalid provider for {platform}: {provider_key}")
        return

    # Save the choice
    bot.set_choice(chat_id, platform, provider_key)

    # Update the message
    provider_name = bot.PROVIDERS[platform]["options"][provider_key]
    try:
        await query.edit_message_text(
            f"✅ Provider for {platform.upper()} set to: {provider_name}",
            reply_markup=None
        )
    except Exception:
        logger.exception("Failed to update callback query message")
        try:
            await query.edit_message_text(
                f"✅ Provider for {platform.upper()} set to: {provider_name}"
            )
        except Exception:
            pass


async def handle_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle new member welcome messages."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.message
    if not msg:
        return

    # Check if this is a new member joining
    if msg.new_chat_members:
        for new_member in msg.new_chat_members:
            if new_member.id == context.bot.id:
                # The bot was added to a chat
                chat_id = msg.chat_id
                try:
                    welcome_msg = (
                        f"👋 Thanks for adding me to this chat!\n"
                        f"I automatically rewrite social media links to use privacy-friendly frontends.\n\n"
                        f"🔧 Available commands:\n"
                        f"/help - Show all commands\n"
                        f"/platform - Manage provider settings\n"
                        f"/version - Show bot version\n\n"
                        f"🔒 Privacy-focused: All links are rewritten to use privacy-frontends like vxtwitter.com, tnfk.com, etc.\n"
                        f"📊 Statistics: Use /stats to see link rewriting counts\n"
                        f"📥 Settings: Use /export to backup your chat settings"
                    )
                    await context.bot.send_message(chat_id=chat_id, text=welcome_msg)
                except Exception as e:
                    logger.exception("Failed to send welcome message: %s", e)
                break

    # Check if this is a left member (bot removed)
    if msg.left_chat_member:
        if msg.left_chat_member.id == context.bot.id:
            # The bot was removed from a chat
            chat_id = msg.chat_id
            logger.info("Bot removed from chat %s", chat_id)


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle channel posts for link rewriting."""
    # Import bot inside function to avoid circular imports
    import bot
    msg = update.channel_post
    if not msg or not msg.text:
        return
    if msg.from_user and msg.from_user.is_bot:
        return
    if bot.is_duplicate_update(update.update_id):
        return

    chat_id = msg.chat_id
    user_id = msg.from_user.id if msg.from_user else 0
    chat_settings = database.get_chat_settings(chat_id, user_id)

    if not chat_settings["enabled"]:
        return
    if bot.is_user_muted(chat_id, user_id):
        # For channel posts, we can't delete the original message, so just don't rewrite
        return
    if chat_settings.get("ignore_forwards", 1) and bot.is_forwarded(msg):
        return
    if bot.is_user_optout(chat_id, user_id):
        return   # user opted out of link rewriting
    if not bot.check_rate(chat_id, user_id, int(chat_settings.get("rate_limit", bot.RATE_LIMIT)), int(chat_settings.get("rate_window", bot.RATE_WINDOW))):
        return

    # Import bot inside function to avoid circular imports
    import bot
    new_text, changed, first_fixed_url, platform, first_preview_url, fixed_count, fixed_platforms, first_raw_url = await bot.process_text(msg.text, chat_id, chat_settings)
    if not changed:
        return

    reply_to = msg.message_id
    sender_name = helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or ""
    preview = helpers.LinkPreviewOptions(
        is_disabled=False,
        url=first_preview_url,
        prefer_large_media=True,
        show_above_text=False,
    ) if first_fixed_url else None

    logger.info("Fixed channel post link in chat %s for user %s", chat_id, user_id)
    try:
        sent_msg = await helpers.safe_send_text(context, chat_id, helpers.format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url), link_preview_options=preview, parse_mode="HTML")
        for plat in fixed_platforms:
            bot.increment_stat(chat_id, plat, user_id)
        if sent_msg and first_raw_url:
            bot.store_rewrite(chat_id, sent_msg.message_id, first_raw_url,
                              helpers.sender_label(msg.from_user, chat_settings["sender_mode"]) or "")
        if sent_msg and first_preview_url and fixed_count == 1:
            asyncio.create_task(
                helpers._warn_if_restricted(context, chat_id, sent_msg.message_id, first_preview_url, helpers.format_repost_text(msg.from_user, chat_settings["sender_mode"], platform=platform, url=first_fixed_url))
            )
    except Exception:
        logger.exception("Failed to send reply for channel post in chat %s")


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    if isinstance(context.error, Conflict):
        logger.warning("Conflict: another instance may be running. Ignoring.")
        return
    logger.exception("Unhandled exception for update %s", update, exc_info=context.error)


# Initialize command handlers
def setup_handlers(application):
    """Set up all command handlers in the application."""
    # Import bot inside function to avoid circular imports
    import bot
    # Import filters inside function to avoid circular imports
    from telegram.ext import filters
    # Register command handlers from PUBLIC_CMDS and ADMIN_CMDS
    for cmd, handler in PUBLIC_CMDS.items():
        application.add_handler(MessageHandler(filters.Command(cmd) & ~filters.UpdateType.EDITED_MESSAGE, handler))

    for cmd, handler in ADMIN_CMDS.items():
        application.add_handler(MessageHandler(filters.Command(cmd) & ~filters.UpdateType.EDITED_MESSAGE, handler))

    # Register other handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.UpdateType.EDITED_MESSAGE, handle_message))
    application.add_handler(MessageHandler(filters.CAPTION, handle_caption))
    application.add_handler(
        MessageHandler(
            filters.UpdateType.EDITED_MESSAGE & filters.TEXT,
            handle_edit,
        )
    )
    application.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, handle_channel_post))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.Document.ALL & filters.CaptionRegex(r"^/import"), handle_import_document))
    application.add_handler(InlineQueryHandler(handle_inline_query))
    application.add_handler(CallbackQueryHandler(handle_callback_query, pattern=r"^provider_"))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS | filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_welcome))


async def is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, chat_type: str) -> bool:
    """Check if a user is an administrator in a chat."""
    try:
        if chat_type == "private":
            return True  # In private chats, the user is always admin
        member = await context.bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def get_choice(chat_id: int, platform: str) -> str:
    """Get the user's choice of provider for a platform."""
    # Import bot inside function to avoid circular imports at module level
    import bot
    return bot.get_choice(chat_id, platform)


def set_choice(chat_id: int, platform: str, provider_key: str) -> None:
    """Set the user's choice of provider for a platform."""
    # Import bot inside function to avoid circular imports at module level
    import bot
    bot.set_choice(chat_id, platform, provider_key)


# Public interface - these are the functions that will be imported by bot.py
__all__ = [
    "handle_message",
    "handle_caption",
    "handle_edit",
    "handle_channel_post",
    "handle_document",
    "handle_import_document",
    "handle_inline_query",
    "handle_callback_query",
    "handle_welcome",
    "handle_error",
    "setup_handlers",
    "is_admin",
    "get_choice",
    "set_choice"
]