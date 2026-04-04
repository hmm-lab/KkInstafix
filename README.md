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

- Instagram: `ee`
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

- `/providers` — show current providers and options.
- `/status` or `/config` — show current chat settings.
- `/about`, `/credits`, `/me` — about / credits message.
- `/mehrab`, `/mo`, `/genius` — send the custom image.

### Admin only

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

## Supported platforms and provider keys

| Platform | Provider keys |
|---|---|
| instagram | `ee`, `vx`, `kk`, `dd`, `ez`, `fxig` |
| twitter | `vx`, `fx`, `fixvx`, `fixupx`, `ez` |
| tiktok | `tnk`, `vx`, `tik`, `tfx`, `ez` |
| reddit | `vx`, `rx`, `rxy`, `ez` |
| facebook | `ez`, `fx`, `bed` |
| threads | `fix`, `vx` |
| bluesky | `bskx`, `bsyy`, `xbsky`, `fx`, `vx`, `cbsky` |
| pixiv | `ph` |
| tumblr | `tp`, `txt` |
| bilibili | `vx`, `fx`, `ez` |
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
- `30364.jpg` — image used by `/mehrab`, `/mo`, `/genius`, `/about`, `/credits`, `/me`.
- `Procfile` — start command.
- `requirements.txt` — Python dependencies.
- `bot_data.sqlite3` — auto-created SQLite database.

## Deploy on Railway

1. Push the repo to GitHub.
2. Create a new Railway project from the repo.
3. Add environment variable `BOT_TOKEN`.
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
