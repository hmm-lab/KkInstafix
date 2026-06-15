# KkInstafix

Telegram bot that rewrites social media links so Telegram previews work better.

It supports Instagram, Twitter/X, TikTok, Reddit, Facebook, Threads, Bluesky, Pixiv, Tumblr, Bilibili, Snapchat, Spotify, Twitch, iFunny, FurAffinity, DeviantArt, and Dribbble.

Current version: **1.2.0** — see [CHANGELOG.md](CHANGELOG.md) for release history.

## Features

- Rewrites supported links automatically — in messages, captions, and edited messages.
- Keeps Telegram link previews enabled with large media previews when possible.
- Preserves reply chains when reposting fixed links.
- Multi-link support: messages with more than one link get all links fixed.
- Supports captioned media posts with links.
- Short-link expansion: `vm.tiktok.com`, `redd.it`, etc. are followed to the real URL first.
- No-account providers (🌐): choose a privacy-friendly frontend for the clickable link while still getting a rich Telegram preview from the embed provider.
- Per-message provider switch: every fixed link gets a **🔁 Embed not working?** button so anyone can cycle to a different provider if a preview renders badly — no admin rights needed.
- Deduplicates repeated links, stickers, GIFs, and repeated plain text spam.
- Per-user rate limiting.
- Inline mode: use `@KkInstaFixBot <link>` in any chat without adding the bot.
- Interactive `/menu` for admins to change providers with inline buttons.
- Command autocomplete in Telegram (registered via `setMyCommands`).
- Admin-only moderation and config commands.
- SQLite storage so settings survive restarts.
- In-memory caches for settings, providers, mutes, dedup, and rate limiting — zero DB reads on the hot path.
- Provider fallback if one fixer host is down (parallel health checks).
- Welcome message when added to a new group.
- File ID caching: photos and videos are uploaded once, then reused instantly.
- Webhook secret token support for secure deployments.
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
- Dribbble: `tv`

## Commands

### Public

- `/start` — welcome message (DM-aware: different text in private chats vs groups).
- `/help` — full command reference.
- `/providers` — show current providers and options (active provider in bold).
- `/status` or `/config` — show current chat settings (human-readable).
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
- `/resetproviders` — reset all providers to defaults (shows what changed).
- `/muteuser` — mute a user by replying to them or by user ID.
- `/unmuteuser` — unmute a user by replying to them or by user ID.
- `/listmuted` — list all muted users with names.
- `/setsendermode first_name|username|full_name|none` — change repost name format.
- `/setdedup <seconds>` — change dedup window.
- `/setratelimit <count> <seconds>` — change rate limit window.
- `/ignoreforwards on|off` — ignore forwarded posts or not.
- `/fallback on|off` — enable or disable provider fallback.
- `/textspam on|off` — enable or disable repeated text deletion.
- `/resetstats` — clear this chat's link-fix stats.
- `/testall <platform>` — test all providers for a platform (runs in parallel).
- `/testall <platform> <url>` — test all providers with a custom URL.
- `/export` — download a JSON backup of this chat's settings, providers and mutes.
- `/import` — send a JSON backup as a document with caption `/import` (or reply to one) to restore. Warns if the backup is from a different chat.

## Supported platforms and provider keys

| Platform | Provider keys |
|---|---|
| instagram | `kkclip`, `kk`, `ee`, `vx`, `ez`, `fxig` |
| twitter | `vx`, `fx`, `fixvx`, `fixupx`, `ez`, `xcancel` 🌐 |
| tiktok | `tnk`, `vx`, `tik`, `tfx`, `ez`, `proxitok` 🌐 |
| reddit | `vx`, `rx`, `rxy`, `ez`, `redlib` 🌐 |
| facebook | `ez`, `fx`, `bed` |
| threads | `fix`, `vx` |
| bluesky | `bskx`, `bsyy`, `bskye`, `xbsky`, `fx`, `vx`, `cbsky` |
| pixiv | `ph`, `pp` |
| tumblr | `tp`, `txt` |
| bilibili | `vx`, `fx` |
| snapchat | `ez` |
| spotify | `fx`, `fix` |
| twitch | `fx` |
| ifunny | `ez` |
| furaffinity | `xfa`, `fxr` |
| deviantart | `fix`, `fx` |
| dribbble | `tv` |

🌐 = **no-account frontend**. When selected, the Telegram preview still loads from the best embed provider, but the clickable link goes to a privacy-friendly frontend where users can view posts without logging in (e.g. xcancel for Twitter, redlib for Reddit, ProxiTok for TikTok).

## Short-link expansion

The bot automatically follows redirects for short/mobile share URLs before applying the provider swap:

- `vm.tiktok.com/...` and `vt.tiktok.com/...` → expanded to full `tiktok.com/@user/video/ID`
- `redd.it/...` → expanded to full `reddit.com/r/sub/comments/...`
- `reddit.com/r/<sub>/s/<id>` → Reddit share links, expanded to the full post URL
- `b23.tv/...` → expanded to full `bilibili.com/video/...`
- `instagram.com/share/...` → processed as Instagram content

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
- `test_bot.py` — pure-function tests (45 tests). Run with `pytest test_bot.py`.
- `bot_data.sqlite3` — auto-created SQLite database.

## Data persistence warning

`bot_data.sqlite3` stores per-chat settings, provider choices, mutes, undo records and stats. On Railway's default filesystem this is **ephemeral** — if the container is rebuilt, the file is lost and all chats fall back to defaults.

To protect against loss:
1. Attach a Railway persistent volume (e.g. mounted at `/data`) and set the `DATA_DIR` environment variable to its mount path — the database is then created inside the volume and survives redeploys, or
2. Use `/export` periodically and save the JSON backup, restoring with `/import` after a wipe.

For a fully managed alternative, port the storage layer to Postgres.

## Deploy on Railway

1. Push the repo to GitHub.
2. Create a new Railway project from the repo.
3. Add environment variables:
   - `BOT_TOKEN` — required.
   - `WEBHOOK_URL` — recommended. Set to your Railway public URL (e.g. `https://your-app.railway.app`). Enables webhook mode, which is more reliable than polling. Leave unset to use polling instead.
   - `WEBHOOK_SECRET` — optional. If set, the bot verifies that incoming webhook requests include this token, preventing fake updates from anyone who guesses the URL.
   - `DATA_DIR` — optional. Path of a persistent volume mount (e.g. `/data`) where the SQLite database is stored, so settings and stats survive redeploys.
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
- Instagram default is `kkclip`.
- Caption link fixing replies with corrected links instead of re-uploading media.
- Edited messages with links are detected and fixed automatically.
- Settings are stored per chat.
- The database is created automatically on startup.
- All frequently-accessed data is cached in memory at startup — the bot does zero DB reads on the hot path.

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
