# kkInstaFixBot

This bot watches your Telegram group. When someone sends an Instagram link, the bot automatically replaces it with a version that plays the video directly inside Telegram â€” no need to open Instagram.

---

## Before and after

Someone sends:
```
https://www.instagram.com/reel/DWIweXbE-Ja/?igsh=aXVsNmx2bm9yNHht
```

Bot deletes it and reposts as:
```
[Instagram] John (@johndoe):
https://www.kkinstagram.com/reel/DWIweXbE-Ja/
```
The video now plays directly inside Telegram.

---

## How to set it up

### Step 1 - Create the bot on Telegram

1. Open Telegram
2. Search for **@BotFather** and open it
3. Tap **Start**
4. Type `/newbot` and send it
5. It will ask: *"What's the name of your bot?"*
   Type something like `KK Insta Fix` and send
6. It will ask: *"What username do you want?"*
   Type something like `KkInstaFixBot` â€” it must end in the word `bot`
7. BotFather will send you a **token** â€” a long code like:
   ```
   7654321234:AAHDzGaiRtHHmeOyiMaolP6L8UdiAEvqDjE
   ```
   Copy this and save it somewhere safe. **Do not share it with anyone.**

---

### Step 2 - Allow the bot to read messages

By default bots cannot see messages unless someone mentions them. Fix this:

1. In the same **@BotFather** chat, type `/mybots` and send
2. Tap your bot's name
3. Tap **Bot Settings**
4. Tap **Group Privacy**
5. Tap **Turn off**
6. You should see: *"Privacy mode is disabled"*

---

### Step 3 - Put the files on GitHub

GitHub is a free website that stores your code. Railway (in the next step) reads from it.

1. Go to https://github.com â€” sign up for free if you don't have an account
2. After logging in, tap the **+** button at the top right
3. Tap **New repository**
4. In the Name box, type: `kkinstagram-bot`
5. Leave everything else as default and tap **Create repository**
6. On the next page, tap the link that says **uploading an existing file**
7. Drag and drop all 4 files onto the grey box: bot.py, requirements.txt, Procfile, README.md
8. Scroll down and tap **Commit changes**

> The files must keep their exact names. `bot.py` not `bot (1).py`, `Procfile` not `procfile` or `Procfile.txt`.

---

### Step 4 - Run it for free on Railway

Railway is a free hosting service. It will keep your bot running 24/7 in the cloud.

1. Go to https://railway.app
2. Tap **Login** â†’ **Login with GitHub** â†’ approve the connection
3. Tap **New Project**
4. Tap **Deploy from GitHub repo**
5. Select your `kkinstagram-bot` repo
6. Railway will start building â€” it may show **FAILED** in red, that is fine for now
7. Tap the **Variables** tab (along the top)
8. Tap **New Variable**
9. In the Name box type: `BOT_TOKEN`
10. In the Value box paste: your token from Step 1
11. Tap **Add**
12. Railway will automatically try again â€” wait about 30 seconds
13. When you see a green **Active** status, the bot is running

---

### Step 5 - Add the bot to your Telegram group

1. Open your Telegram group
2. Tap the group name at the top to open its info page
3. Tap **Add Members**
4. Search for your bot username (e.g. `@KkInstaFixBot`)
5. Tap it, then tap **Add**
6. Now make it an admin so it can delete messages:
   - Tap the group name again â†’ **Edit** (pencil icon) â†’ **Administrators**
   - Tap **Add Admin**
   - Find and tap your bot
   - Make sure **Delete Messages** has a tick next to it
   - Tap **Done**

That's everything. Try sending an Instagram link in the group.

---

## Something went wrong?

| What you see | What to do |
|---|---|
| Bot does nothing when a link is sent | Go back to Step 2 and make sure Privacy Mode is turned OFF |
| Railway shows "Railpack error" | Check that the `Procfile` file exists and contains: `worker: python bot.py` |
| Bot reposts but can't delete the original | Go back to Step 5 and check Delete Messages is ticked in Admin settings |
| Railway shows a token error | Go to Railway â†’ Variables tab and check BOT_TOKEN is set correctly |

---

## Updating the bot later

1. Open your GitHub repo
2. Tap the filename you want to change (e.g. `bot.py`)
3. Tap the **pencil icon** (top right of the file)
4. Make your edit
5. Tap **Commit changes**

Railway will automatically restart with the new code within about a minute.

---

## Cost

Railway gives you free credit to start. This bot typically costs under Â£1/month to run, well within the free allowance for several months.
