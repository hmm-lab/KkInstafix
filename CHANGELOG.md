# Changelog

All notable changes to KkInstafix are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.11.0] - 2026-06-15

### Added
- **Continuous integration** — a GitHub Actions workflow (`.github/workflows/tests.yml`)
  runs the full `pytest` suite on Python 3.11 and 3.12 for every push and pull
  request, plus a no-network smoke test of the provider checker's URL builder.
  The test suite previously only ran locally; now regressions are caught on push.

### Changed
- `.gitignore` now also excludes `.pytest_cache/`.

## [1.10.0] - 2026-06-15

### Changed
- **`/clean` now cleans as thoroughly as a rewrite** — previously it only applied
  the conservative *generic* strip, so `/clean` on a Twitter link left `?s=20&t=`
  and on a TikTok link left session junk. A new host-aware `clean_url` helper
  removes a known platform's share tokens (the global list plus that platform's
  `PLATFORM_TRACKING`) while keeping the original host, and still falls back to
  the YouTube-aware, fragment-preserving generic strip for everything else.

## [1.9.0] - 2026-06-15

### Fixed
- **Tracking-token leak on rewritten Twitter/X and TikTok links** — rewriting a
  tweet kept Twitter's `?t=<token>` share token (only `s` was stripped), and
  rewritten TikTok links kept `is_from_webapp`, `sender_device`, `_t` and other
  session junk. These keys are unambiguous tracking on their platform but
  meaningful elsewhere (`t` is a YouTube timestamp), so they're stripped via a
  new per-platform `PLATFORM_TRACKING` map applied during rewriting rather than
  the global list. The 🔁 provider-cycle button benefits too, since it shares the
  same `apply_provider` path. Non-tracking query params on other platforms (e.g.
  Reddit `?context=3`) are preserved.

## [1.8.0] - 2026-06-15

### Added
- **YouTube `/live/` and `m.youtube.com` normalization** — the Shorts converter
  now also handles `youtube.com/live/<id>` and the mobile `m.youtube.com` host,
  rewriting both to a canonical `youtube.com/watch?v=<id>` URL. A start-time
  param (`t` or `start`) is preserved when present, and share/tracking params
  like `si`/`feature` are dropped.

## [1.7.0] - 2026-06-15

### Added
- **YouTube-scoped share-param stripping** — YouTube share links sometimes carry
  `?is=<token>` (a variant of the usual `?si=`). `is` and `pp` are too generic to
  strip from arbitrary sites, so they are now removed only when the host is
  YouTube (`youtube.com`, `youtu.be`, `m.`/`music.youtube.com`). Essential params
  like `v` (video id) and `t` (timestamp) are preserved.

## [1.6.0] - 2026-06-15

### Fixed
- **Substring corruption when rewriting multiple links** — `process_text` built
  the output with `str.replace(raw, fixed)`, which replaces every occurrence
  *and substring*. When one URL token was a string prefix of another in the same
  message (e.g. `.../p?utm_id=1` inside `.../p?utm_id=1&keep=2`), fixing the
  shorter link corrupted the longer one (the example mangled to `.../p&keep=2`).
  Rewriting now happens in a single regex pass that matches whole URL tokens
  exactly, so links can no longer clobber each other.

## [1.5.0] - 2026-06-15

### Added
- **`tools/check_providers.py`** — a standalone provider health checker. It
  builds a fixed URL for every provider host (reusing the bot's own
  `SAMPLE_URLS` + `apply_provider`, so it never drifts from real behaviour),
  fetches each with Telegram's preview-crawler User-Agent, and prints an
  UP/DOWN table with embed (Open Graph) detection. Supports `--platform`,
  `--json`, and `--timeout`; exit code equals the number of DOWN hosts so it
  can gate CI. Detects and warns when every host returns the same proxy error
  (i.e. you're running behind an egress allowlist and the result is meaningless).
- **`SAMPLE_URLS` coverage guard test** — fails loudly if a platform is added
  without a sample URL, which would otherwise silently skip it in both
  `/testall` and the health checker.

## [1.4.0] - 2026-06-15

### Added
- **`t.co` Twitter short-link expansion** — `t.co/<id>` wrapper links (produced
  whenever a link is copied out of a tweet) are now unwrapped to their target
  before processing. If the target is a known platform it gets fixed; otherwise
  it's tracking-stripped like any other plain link.
- **Expanded generic tracking list** — now also strips Facebook/Meta mobile
  share identifiers (`mibextid`, `extid`), Reddit web tracking (`rdt`), and
  several vendor-documented campaign/analytics identifiers (`ncid`, `cmpid`,
  `_branch_referrer`, `oly_enc_id`, `oly_anon_id`). The list stays conservative —
  ambiguous keys like `s`/`ref`/`hl` are still left alone.

## [1.3.0] - 2026-06-15

### Added
- **`youtu.be` short-link expansion** — `youtu.be/VIDEO_ID` links now expand to
  `youtube.com/watch?v=VIDEO_ID` before tracking stripping, producing a clean,
  canonical URL instead of the short link.
- **Instagram `/share/` expansion** — `instagram.com/share/<id>` share links are
  now expanded to the real post URL before provider rewriting, so the fixer
  provider receives a valid `/p/<id>/` path instead of an untranslated `/share/`
  path.
- **`_expand_cache` LRU eviction** — the short-URL expansion cache now evicts the
  least-recently-used entry when it reaches 2 000 items, instead of silently
  stopping to cache new entries.

### Fixed
- **`fix_url` silent expansion drop** — when a short link expanded to a URL that
  had no additional tracking params to strip (e.g. `youtu.be/abc` with no `?si=`),
  the expansion was discarded and the original short URL was returned unchanged.
  Fixed by comparing the cleaned result against the pre-expansion URL.

### Changed
- **`handle_edit` rate limiting** — edited messages with links are now subject to
  the same per-user rate limit as regular messages, closing an exploit where
  repeatedly editing a message could bypass rate limiting.
- **`seen_recent` hot-path cleanup removed** — the O(n) dedup-cache scan that
  triggered inline on the 100 001st entry is moved to the hourly `cleanup_db`
  job, with a 500 000-entry safety cap that clears the cache entirely if the
  periodic job can't keep up.
- **`check_rate` O(1) eviction** — rate-limit timestamp windows now use
  `collections.deque` with `popleft()` instead of `list.pop(0)`, reducing
  eviction cost from O(n) to O(1).

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
