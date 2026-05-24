# KkInstafix

Telegram bot that rewrites social media links so Telegram previews work better.

It supports Instagram, Twitter/X, TikTok, Reddit, Facebook, Threads, Bluesky, Pixiv, Tumblr, Bilibili, Snapchat, Spotify, Twitch, iFunny, FurAffinity, and DeviantArt.

## Features

- Rewrites supported links automatically.
- Keeps Telegram link previews enabled with large media previews when possible.
- Preserves reply chains when reposting fixed links.
- Supports captioned media posts with links.
- Deduplicates repeated links, stickers, GIFs, and repeated plain text spam.
- Per-user rate limiting.
- Admin-only moderation and config commands.
- SQLite storage so settings survive restarts.
- Provider fallback if one fixer host is down.
- Welcome message when added to a new group.
- About / credits commands with custom image support.

## Default providers

- Instagram: `kkclip`
- Twitter/X: `vx`
- TikTok: `tnk`
- Reddit: `vx`
- Facebook: `ez`
- Threads: `fix`
- Bluesky: `bskx`
- Pixiv: `ph`
- Tumblr: `tp`
- Bilibili: `vx`
- Snapchat: `ez`
- Spotify: `fx`
- Twitch: `fx`
- iFunny: `ez`
- FurAffinity: `xfa`
- DeviantArt: `fix`

## Commands

### Public

- `/start` — welcome message and quick how-to.
- `/providers` — show current providers and options.
- `/status` or `/config` — show current chat settings.
- `/stats` — show per-chat rewrite counts and top senders.
- `/undo` — reply to a rewritten message with `/undo` to see the original link (7-day retention).
- `/about`, `/credits`, `/me` — about / credits message.
- `/mehrab`, `/mo` — send the custom image.
- `/genius` — send the custom video.

### Inline

Type `@KkInstaFixBot <link>` in any chat to get a fixed link result without adding the bot to that chat.

### Admin only

- `/menu` — interactive inline-button provider config.
- `/enable` — enable bot features in this chat.
- `/disable` — disable bot features in this chat.
- `/setprovider <platform> <provider>` — set provider for a platform.
- `/resetproviders` — reset all providers to defaults.
- `/muteuser` — mute a user by replying to them.
- `/muteuser <user_id>` — mute by numeric user ID.
- `/unmuteuser` — unmute a user by replying to them.
- `/unmuteuser <user_id>` — unmute by numeric user ID.
- `/setsendermode first_name|username|full_name|none` — change repost name format.
- `/setdedup <seconds>` — change dedup window.
- `/setratelimit <count> <seconds>` — change rate limit window.
- `/ignoreforwards on|off` — ignore forwarded posts or not.
- `/fallback on|off` — enable or disable provider fallback.
- `/textspam on|off` — enable or disable repeated text deletion.
- `/testall <platform>` — test all providers for a platform.
- `/testall <platform> <url>` — test all providers with a custom URL.
- `/export` — download a JSON backup of this chat's settings, providers and mutes.
- `/import` — send a JSON backup as a document with caption `/import` (or reply to one) to restore.

## Supported platforms and provider keys

| Platform | Provider keys |
|---|---|
| instagram | `kkclip`, `kk`, `ee`, `vx`, `ez`, `fxig` |
| twitter | `vx`, `fx`, `fixvx`, `fixupx`, `ez`, `xcancel` 🌐 |
| tiktok | `tnk`, `vx`, `tik`, `tfx`, `ez`, `proxitok` 🌐 |
| reddit | `vx`, `rx`, `rxy`, `ez`, `redlib` 🌐 |
| facebook | `ez`, `fx`, `bed` |
| threads | `fix`, `vx` |
| bluesky | `bskx`, `bsyy`, `xbsky`, `fx`, `vx`, `cbsky` |
| pixiv | `ph` |
| tumblr | `tp`, `txt` |
| bilibili | `vx`, `fx` |
| snapchat | `ez` |
| spotify | `fx`, `fix` |
| twitch | `fx` |
| ifunny | `ez` |
| furaffinity | `xfa`, `fxr` |
| deviantart | `fix`, `fx` |

## Anti-spam behavior

- Same link can be blocked for a configurable dedup window.
- Same sticker or GIF can be deleted if repeated.
- Same plain text can be deleted if repeated and text spam protection is enabled.
- Muted users can have their messages auto-deleted.
- Repeated webhook / polling updates are ignored.

## Files

- `bot.py` — main bot code.
- `30364.jpg` — image used by `/mehrab`, `/mo`, `/about`, `/credits`, `/me`.
- `genius.mp4` — video used by `/genius`.
- `Procfile` — start command.
- `requirements.txt` — Python dependencies.
- `requirements-dev.txt` — dev dependencies (pytest).
- `test_bot.py` — pure-function tests. Run with `pytest test_bot.py`.
- `bot_data.sqlite3` — auto-created SQLite database.

## Data persistence warning

`bot_data.sqlite3` stores per-chat settings, provider choices, mutes, undo records and stats. On Railway's default filesystem this is **ephemeral** — if the container is rebuilt, the file is lost and all chats fall back to defaults.

To protect against loss:
1. Attach a Railway persistent volume mounted at the project root, or
2. Use `/export` periodically and save the JSON backup, restoring with `/import` after a wipe.

For a fully managed alternative, port the storage layer to Postgres.

## Deploy on Railway

1. Push the repo to GitHub.
2. Create a new Railway project from the repo.
3. Add environment variables:
   - `BOT_TOKEN` — required.
   - `WEBHOOK_URL` — recommended. Set to your Railway public URL (e.g. `https://your-app.railway.app`). Enables webhook mode, which is more reliable than polling. Leave unset to use polling instead.
   - `PORT` — set automatically by Railway; do not override.
4. Make sure the start command uses lowercase:
   - `python bot.py`
5. Deploy.

If you use a `Procfile`, the worker line should also use lowercase:

```procfile
worker: python bot.py
```

## Required bot permissions

In Telegram groups, give the bot these admin permissions if you want full functionality:

- Delete messages
- Read messages
- Post messages / send messages

Without delete permission, the bot can still reply in some cases, but spam cleanup and link replacement will be limited.

## Notes

- Twitter and X are treated as the same platform.
- Instagram default is `ee`.
- Caption link fixing replies with corrected links instead of re-uploading media.
- Settings are stored per chat.
- The database is created automatically on startup.

## Troubleshooting

### Bot starts but does nothing

- Check that `BOT_TOKEN` is set correctly.
- Make sure the bot is added to the group.
- Make sure privacy mode is configured the way you want in BotFather.
- Make sure the bot has permission to delete messages if you expect it to replace messages.

### Conflict: terminated by other getUpdates request

Usually means another instance of the bot is still running somewhere else.

### Preview does not show every time

Telegram preview generation is controlled by Telegram itself, so some providers may still work better than others depending on the link. Use `/testall <platform> <url>` to compare providers.

## Credits

My name is Mehrab and I love you Motki.
