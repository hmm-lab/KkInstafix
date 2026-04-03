# kkInstagram Telegram Bot

Automatically replaces `instagram.com` links with `kkinstagram.com` in your group chat for better Telegram embeds.

---

## Setup (5 minutes)

### 1. Create a bot token
1. Open Telegram and message `@BotFather`
2. Send `/newbot`
3. Follow the prompts (give it a name and username)
4. Copy the **token** it gives you (looks like `123456:ABC-DEF...`)

### 2. Disable Privacy Mode
In BotFather:
1. Send `/mybots`
2. Select your new bot
3. Go to **Bot Settings → Group Privacy → Turn Off**
   *(Without this, the bot can't see messages that don't mention it)*

### 3. Set your token
Open `bot.py` and replace `YOUR_BOT_TOKEN_HERE` with your token,
OR set an environment variable:
```
export BOT_TOKEN="your_token_here"
```

### 4. Install & run
```bash
pip install -r requirements.txt
python bot.py
```

### 5. Add bot to your group
1. Open your Telegram group
2. Go to Add Members → search your bot's username
3. Make it an Admin and enable **Delete Messages** permission

---

## Free Hosting (no server needed)

Deploy for free on [Railway](https://railway.app):
1. Push this folder to a GitHub repo
2. Connect Railway → New Project → Deploy from GitHub
3. Add `BOT_TOKEN` in Railway's Environment Variables tab
4. Done — it runs 24/7 for free

---

## How it works

When someone sends a message containing an `instagram.com` link:
1. Bot deletes the original message
2. Reposts it with the link replaced by `kkinstagram.com`
3. Telegram then generates a proper embed preview

If the bot lacks delete permissions, it falls back to replying with the fixed link.
