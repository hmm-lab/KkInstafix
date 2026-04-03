# -*- coding: utf-8 -*-
import os
import re
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

INSTAGRAM_RE = re.compile(
    r'(https?://(?:www\.)?instagram\.com\S*)',
    re.IGNORECASE
)

TRACKING_PARAMS = {
    'igsh', 'igshid', 'utm_source', 'utm_medium', 'utm_campaign',
    'utm_content', 'utm_term', 'utm_id', 'fbclid', 'ref', 'hl'
}

def fix_instagram_url(url):
    parsed = urlparse(url)
    new_netloc = parsed.netloc.replace('instagram.com', 'kkinstagram.com')
    params = parse_qs(parsed.query, keep_blank_values=True)
    clean_params = {k: v for k, v in params.items() if k.lower() not in TRACKING_PARAMS}
    clean_query = urlencode(clean_params, doseq=True)
    return urlunparse((parsed.scheme, new_netloc, parsed.path, parsed.params, clean_query, ''))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    text = message.text
    if not INSTAGRAM_RE.search(text):
        return

    fixed_text = INSTAGRAM_RE.sub(lambda m: fix_instagram_url(m.group(0)), text)
    if fixed_text == text:
        return

    sender = message.from_user
    name = sender.full_name if sender else "Someone"

    if sender and sender.username:
        username = " (@" + sender.username + ")"
    else:
        username = ""

    newline = chr(10)
    msg = "[Instagram] " + name + username + newline + fixed_text

    try:
        await message.delete()
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=msg,
            disable_web_page_preview=False,
        )
    except Exception:
        await message.reply_text(
            text=msg,
            disable_web_page_preview=False,
        )

def main():
    print("kkInstagram bot starting...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()            disable_web_page_preview=False,
        )

def main():
    print("kkInstagram bot starting...")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()    username = f" (@{sender.username})" if sender and sender.username else ""

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
