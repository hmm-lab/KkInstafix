# Changelog

All notable changes to KkInstafix are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-06-15

This release merges the two development lines together: the feature-rich `main`
codebase and the session branch, then layers the session's requested
adjustments on top.

### Added
- **`/clean`** — reply to a message (or pass `/clean <url>`) to strip tracking
  parameters from its links *without* rewriting them to a fixer provider.
- **`/version`** — report the running bot version. `__version__` now lives in
  `bot.py` as the single source of truth.
- **Generic tracking stripping on non-rewritten links** (e.g. YouTube `?si=`,
  `utm_*`, `fbclid`, and other click identifiers), using a conservative list
  that leaves ambiguous keys like `s`/`ref`/`hl` alone so it never breaks
  search or routing on arbitrary sites.
- **TikTok `/t/<id>` share-link expansion**, alongside the existing
  `vm.tiktok.com`, `vt.tiktok.com`, `redd.it`, `b23.tv`, and Reddit
  `/r/<sub>/s/<id>` expansion.
- This changelog and versioning scheme.

### Changed
- The `/` command autocomplete menu is now **hidden** on startup: instead of
  registering commands via `set_my_commands`, the bot clears them across all
  scopes (default, all-private-chats, all-group-chats, all-chat-admins) so
  users aren't overwhelmed with options. Commands still work when typed.

### Removed
- `/taggay`, `/untaggay`, and `/listgay` commands and the associated
  `tagged_users` storage, cache, and `(gay)` repost suffix.

## [1.1.0] - 2026-06-14

The feature-rich baseline this release builds on.

### Added
- Per-message **🔁 Embed not working?** button to cycle providers, with
  callback routing.
- Restricted/private content detection — warns in the bot message when content
  is inaccessible.
- `/stats`, `/undo`, `/export`, `/import`, interactive `/menu`, and inline mode
  (`@bot <link>`).
- No-account frontend providers (xcancel, redlib, ProxiTok) with separate
  embed-preview pairs.
- Short/mobile share-link expansion and additional providers (Dribbble, etc.).
- `/help` and `/listmuted` commands; file-ID caching; webhook secret support.

## [1.0.0] - 2026-06-11

### Added
- Initial release: automatic rewriting of social media links for better
  Telegram previews across Instagram, Twitter/X, TikTok, Reddit, Facebook,
  Threads, Bluesky, and more.
- Per-chat provider selection, admin moderation/config commands, dedup and
  rate-limit anti-spam, SQLite persistence, and provider fallback.

[1.2.0]: https://github.com/hmm-lab/kkinstafix/releases/tag/v1.2.0
[1.1.0]: https://github.com/hmm-lab/kkinstafix/releases/tag/v1.1.0
[1.0.0]: https://github.com/hmm-lab/kkinstafix/releases/tag/v1.0.0
