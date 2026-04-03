import os
import re
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TOKEN = os.environ.get("BOT_TOKEN")
# Matches any instagram.com URL (with or without www, http or https)
INSTAGRAM_RE = re.compile(
    r'(https?://(?:www\.)?instagram\.com\S*)',
    re.IGNORECASE
)

# â”€â”€ Handler â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    text = message.text

    # Ignore if no Instagram link found
    if not INSTAGRAM_RE.search(text):
        return

    # Replace instagram.com â†’ kkinstagram.com
    fixed_text = INSTAGRAM_RE.sub(
        lambda m: m.group(0).replace('instagram.com', 'kkinstagram.com', 1),
        text
    )

    if fixed_text == text:
        return  # Nothing changed

    sender   = message.from_user
    name     = sender.full_name if sender else "Someone"
    username = f" (@{sender.username})" if sender and sender.username else ""

    # Try to delete the original and repost with fixed link
    try:
        await message.delete()
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=f"ðŸ“¸ {name}{username}:\n{fixed_text}",
            disable_web_page_preview=False,
        )
    except Exception:
        # Fallback: no delete permission â€” just reply with the fixed link
        await message.reply_text(
            text=f"ðŸ“¸ Fixed link:\n{fixed_text}",
            disable_web_page_preview=False,
        )


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main() -> None:
    print("ðŸ¤– kkInstagram bot starting...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
