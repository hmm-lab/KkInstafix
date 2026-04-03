# kkInstaFixBot

This bot rewrites social media links so they preview better in Telegram.

It also lets each Telegram group choose which fixer provider it wants to use for each platform.

## What the bot can do

- Replace Instagram links with a Telegram-friendly provider
- Replace Twitter/X links with a Telegram-friendly provider
- Replace TikTok, Reddit, Threads, Bluesky, Pixiv, and Tumblr links too
- Strip common tracking junk from links
- Convert YouTube Shorts into normal YouTube watch links
- Save provider choices separately for each chat

## Main commands

### Show current providers
Use:

```text
/providers
```

This shows:
- the current provider being used for each platform in this chat
- the list of provider options you can switch to

### Change a provider
Use:

```text
/setprovider <platform> <provider>
```

Examples:

```text
/setprovider instagram ddinstagram
/setprovider twitter fxtwitter
/setprovider x fixupx
/setprovider tiktok tnktok
/setprovider reddit rxyddit
/setprovider bluesky vxbsky
```

### Reset everything back to default
Use:

```text
/resetproviders
```

### Help
Use:

```text
/help
```

## Default providers

These are the defaults the bot starts with:

- instagram -> kkinstagram
- twitter -> vxtwitter
- x -> fixvx
- tiktok -> vxtiktok
- reddit -> rxddit
- threads -> fixthreads
- bluesky -> bskx
- pixiv -> phixiv
- tumblr -> tpmblr

## Available providers

### Instagram
- kkinstagram
- ddinstagram
- eeinstagram
- instagramez

### Twitter
- vxtwitter
- fxtwitter
- twitterez

### X
- fixvx
- fixupx

### TikTok
- vxtiktok
- tnktok
- tfxktok
- tiktxk
- tiktokez

### Reddit
- rxddit
- rxyddit
- redditez

### Threads
- fixthreads

### Bluesky
- bskx
- bsyy
- bskye
- vxbsky
- fxbsky

### Pixiv
- phixiv

### Tumblr
- tpmblr

## How it behaves in the group

When someone sends a supported link:
1. The bot detects the link
2. It rewrites the domain using your chosen provider for that platform
3. It removes tracking parameters when possible
4. It deletes the original message and reposts the cleaned version
5. If it cannot delete the original, it replies instead

## Example

If your group sets:

```text
/setprovider instagram ddinstagram
```

then a link like:

```text
https://www.instagram.com/reel/ABC123/?igsh=xyz
```

can be reposted as:

```text
https://www.ddinstagram.com/reel/ABC123/
```

## Setup reminders

For the bot to work properly in a Telegram group:
- Privacy Mode must be OFF in BotFather
- The bot should be an admin in the group
- The bot should have permission to delete messages if you want clean replacement behavior

## Files in this repo

- `bot.py` -> the bot code
- `requirements.txt` -> Python package list
- `Procfile` -> tells Railway how to run the bot
- `README.md` -> this guide

## Troubleshooting

### The bot does nothing
Check:
- Privacy Mode is turned off in BotFather
- the bot is actually added to the correct group
- the message contains a full `http` or `https` link

### The bot replies instead of replacing
That usually means it does not have permission to delete messages in the group.

### A provider command does not work
Run:

```text
/providers
```

Then copy the platform and provider names exactly as shown.

### Railway deploy fails
Check:
- `BOT_TOKEN` exists in Railway Variables
- `Procfile` contains exactly:

```text
worker: python bot.py
```

## Good first commands to try

```text
/providers
/setprovider instagram ddinstagram
/setprovider twitter fxtwitter
/setprovider x fixupx
```
