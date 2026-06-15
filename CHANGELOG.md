# Changelog

All notable changes to KkInstafix are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-06-15

### Added
- `/clean` command — reply to a message (or pass a URL) to strip tracking
  parameters from its links without rewriting them to a fixer provider.
- `/help` command — a proper command reference, separate from `/providers`.
- `/listmuted` command — list all muted users in the chat by name and ID.
- `/version` command — report the running bot version.
- Tracking parameters are now stripped from links that are **not** rewritten,
  such as YouTube (`?si=`), `utm_*`, `fbclid`, and other click identifiers,
  using a conservative list that leaves ambiguous keys (`s`, `ref`, `hl`) alone.
- `/start` now shows a DM-aware greeting with the supported-platform list.
- Pure-function test suite (`test_bot.py`).

### Changed
- Command output is formatted with HTML and platform emojis; `/providers`
  bolds the active provider and `/status` uses a clearer layout.
- Toggle commands (`/ignoreforwards`, `/fallback`, `/textspam`) now describe
  what the new state does instead of printing `True`/`False`.
- `/setdedup` and `/setratelimit` report when a value was clamped to range.
- `/muteuser` and `/unmuteuser` resolve the user's name and guard against
  muting an already-muted user (or unmuting one who isn't muted).
- `/about` is rendered as HTML (was Markdown), fixing literal `*`/`_` in some
  Telegram clients.
- The "/" command autocomplete menu is hidden on startup (commands are cleared
  across all scopes) so users aren't overwhelmed with options; commands still
  work when typed.

### Fixed
- Deduplication keys now strip tracking, so the same post shared with different
  tracking parameters is correctly treated as a duplicate.
- Rate limiting only counts messages that contain a link, not plain text.
- The welcome handler uses `context.bot.id` instead of an extra `get_me()` call.

### Removed
- `/taggay`, `/untaggay`, and `/listgay` commands and the associated
  `tagged_users` storage.

## [1.0.0] - 2026-06-11

### Added
- Initial tracked release: automatic rewriting of social media links for
  better Telegram previews across Instagram, Twitter/X, TikTok, Reddit,
  Facebook, Threads, Bluesky, and more.
- Per-chat provider selection, admin moderation and config commands,
  dedup/rate-limit anti-spam, SQLite persistence, and provider fallback.

[1.1.0]: https://github.com/hmm-lab/kkinstafix/releases/tag/v1.1.0
[1.0.0]: https://github.com/hmm-lab/kkinstafix/releases/tag/v1.0.0
