# KkInstafix

![tests](https://github.com/hmm-lab/kkinstafix/actions/workflows/tests.yml/badge.svg)

Telegram bot that rewrites social media links so Telegram previews work better.

It supports Instagram, Twitter/X, TikTok, Reddit, Facebook, Threads, Bluesky, Pixiv, Tumblr, Bilibili, Snapchat, Spotify, Twitch, iFunny, FurAffinity, DeviantArt, and Dribbble.

Current version: **1.19.0** — see [CHANGELOG.md](CHANGELOG.md) for release history.

## Features

- Rewrites supported links automatically — in messages, captions, and edited messages.
- Keeps Telegram link previews enabled with large media previews when possible.
- Preserves reply chains when reposting fixed links.
- Multi-link support: messages with more than one link get all links fixed.
- Supports captioned media posts with links.
- Short-link expansion: `vm.tiktok.com`, `redd.it`, `b23.tv`, etc. are followed to the real URL first (`youtu.be` and YouTube Shorts/Live are rewritten by path, no network).
- Strips tracking parameters even from links it doesn't rewrite (e.g. YouTube `?si=`, `utm_*`, `fbclid`), using a conservative list that leaves ambiguous keys like `s`/`ref` alone. Platform-specific tracking is also stripped for Amazon, eBay, AliExpress, LinkedIn, Pinterest, Apple Music, Vimeo, and SoundCloud.
- Strips platform-specific share tokens when rewriting (Twitter/X `?t=`, TikTok session/referrer params) so reposted links carry no tracking.
- No-account providers (🌐): choose a privacy-friendly frontend for the clickable link while still getting a rich Telegram preview from the embed provider.
- Per-message provider switch: every fixed link gets a **🔁 Embed not working?** button so anyone can cycle to a different provider if a preview renders badly — no admin rights needed.
- Deduplicates repeated links, stickers, GIFs, and repeated plain text spam.
- Per-user rate limiting.
- Inline mode: use `@KkInstaFixBot <link>` in any chat without adding the bot.
- Interactive `/menu` for admins to change providers with inline buttons.
- Commands are intentionally hidden from the Telegram "/" autocomplete menu to keep the UI uncluttered — they still work when typed.
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
- `/clean` — reply to a message (or pass a URL) to strip tracking from its links without rewriting them (host-aware: removes platform share tokens like Twitter `?t=` too).
- `/version` — show the running bot version.
- `/about`, `/credits`, `/me` — about / credits message.
- `/mehrab`, `/mo` — send the custom image.
- `/genius` — send the custom video.

### Inline

Type `@KkInstaFixBot <link>` in any chat to get a fixed link result without adding the bot to that chat. Works for rewritable platforms and also offers a tracking-cleaned result for YouTube and other links.

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
- `tiktok.com/t/<id>` → TikTok share links, expanded to the full video URL
- `b23.tv/...` → expanded to full `bilibili.com/video/...`
- `instagram.com/share/<id>` → expanded to the real post URL before provider rewriting
- `t.co/<id>` → Twitter's link wrapper, unwrapped to its target (then fixed or tracking-stripped)
- `amzn.to/...` → expanded to full Amazon product URL
- `maps.app.goo.gl/...` → expanded to Google Maps URL
- `pin.it/...` → expanded to Pinterest URL
- `bit.ly`, `tinyurl.com`, `t.ly`, `ow.ly`, `is.gd`, `rb.gy`, `buff.ly`, `goo.gl` → expanded to their destination before tracking is stripped

YouTube `youtu.be/<id>`, `/shorts/<id>` and `/live/<id>` URLs (the latter two on `youtube.com` and `m.youtube.com`) are normalized to a canonical `youtube.com/watch?v=<id>` link — a `t`/`start` timestamp is kept, share/tracking params (`?si=`, `?is=`, `?feature=`) are dropped. This is a path rewrite, **not** a redirect, so it works without network access — important because following a `youtu.be` redirect from a server IP can hit a Google CAPTCHA page instead of the video.

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
- `test_bot.py` — pure-function tests (82 tests). Run with `pytest test_bot.py`.
- `test_handlers.py` — async handler tests with lightweight fakes (21 tests covering every update handler). Run the whole suite with `pytest`.
- `tools/check_providers.py` — provider health checker (run from a host with open network).
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

### Checking which providers are up

Run the health checker from a machine with open outbound network:

```bash
python tools/check_providers.py            # all platforms
python tools/check_providers.py --platform twitter
python tools/check_providers.py --json
```

It prints an UP/DOWN table with embed (Open Graph) detection and exits with the number of down hosts. **Don't run it from a sandbox with an egress allowlist** — every host will return the same proxy error and the result is meaningless (the script warns when it detects this). Inside Telegram, `/testall <platform>` is the equivalent live check.

## Credits

My name is Mehrab and I love you Motki.
