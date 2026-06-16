# Changelog

All notable changes to KkInstafix are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.27.0] - 2026-06-16

### Changed
- **`"feature"` removed from `GENERIC_TRACKING`** — `?feature=` was being
  stripped from every URL, which could break legitimate feature-flag or
  UI-variant parameters on non-YouTube sites. It is still stripped on YouTube
  hosts via `YOUTUBE_TRACKING` where it is a documented share/analytics param.
- **`strip_generic_tracking` refactored to use `HOST_TRACKING_MAP`** — the
  nine sequential `if host in <set>` blocks are replaced by a single
  `HOST_TRACKING_MAP.get(host)` lookup. The map is built once at import time
  from the existing domain-set constants, so behaviour is identical but the
  code is O(1) per call and trivially extensible.

### Fixed
- No behaviour change for any currently-tracked URL — all 130 tests pass.

## [1.26.0] - 2026-06-16

### Added
- **Pinterest regional domain coverage** — `PINTEREST_DOMAINS` expanded from
  12 to 24 entries, adding `.nl`, `.be`, `.in`, `.jp`, `.ru`, `.mx`, `.nz`,
  `.ie`, `.sg`, `.cz`, `.gr`, `.br`. Tracking strip now works on all
  major regional Pinterest sites.
- **LinkedIn tracking params** — `sessionRedirect`, `liuid`, and `midMgmt`
  added to `LINKEDIN_TRACKING`. These are seen on LinkedIn mobile share links.

### Changed
- **Welcome message and `/help` updated** — `WELCOME_TEXT` now mentions
  tracking strip for Amazon, eBay, AliExpress, and LinkedIn. The `/clean`
  help line notes that it expands short links before cleaning.

## [1.25.0] - 2026-06-16

### Added
- **AliExpress regional domain coverage** — `ALIEXPRESS_DOMAINS` expanded from
  3 entries to 15, covering `aliexpress.de`, `.fr`, `.es`, `.it`, `.co.uk`,
  `.com.br`, `.nl`, `.pl`, `.at`, `.ch`, `.se`, `.be`. Tracking strip previously
  silently skipped all regional stores.

### Changed
- **`/testall` error message names the platform** — if a platform has no sample
  URL, the reply now says "No sample URL for **instagram**" instead of the generic
  hint, making it clear whether it's a bot gap or a user error.
- **Inline "already clean" hint** — when a user types a link that has no tracking
  to remove and no provider to swap, the inline result now reads "All links already
  clean" instead of "No supported link found", which was misleading.

## [1.24.0] - 2026-06-16

### Added
- **eBay regional TLD coverage** — `EBAY_TLDS` now includes `ebay.at`, `ebay.pl`,
  `ebay.nl`, `ebay.ch`, `ebay.se`, and `ebay.be`. Tracking strip previously
  silently skipped these European stores.

### Changed
- **Inline mode shows destination domain** — the `🧹 Clean link` inline result
  title now reads `🧹 Clean link → youtube.com` (or whatever the destination
  domain is), so users can verify where a short link resolves before sending it.

## [1.23.0] - 2026-06-16

### Added
- **Amazon regional store coverage** — `AMAZON_TLDS` now includes
  `amazon.com.tr` (Turkey), `amazon.com.be` (Belgium), `amazon.pl` (Poland),
  `amazon.eg` (Egypt), and `amazon.co.za` (South Africa). Tracking strip and
  ASIN extraction previously silently skipped these stores.

## [1.22.0] - 2026-06-16

### Fixed
- **`/clean` now path-rewrites `youtu.be` links** — `clean_url_expanded` had
  the short-link expansion and Amazon ASIN logic but missed the `youtu.be`
  path rewrite, so `/clean https://youtu.be/abc?si=x` returned the raw
  `youtu.be` URL (tracking stripped) instead of the canonical
  `youtube.com/watch?v=abc`. The same path-rewrite logic used in `fix_url`
  is now applied first, before falling back to `clean_url`.
- **`SOUNDCLOUD_TRACKING` cleaned up** — `"si"` was redundant (already in
  `GENERIC_TRACKING`). `"ref"` is correctly kept platform-scoped because it
  is intentionally *not* in `GENERIC_TRACKING` (too ambiguous to strip from
  arbitrary sites).

### Added
- **Handler tests for `/clean` command** — two new tests in `test_handlers.py`
  exercise the `/clean` command end-to-end: youtu.be path rewriting and inline
  URL argument cleaning with platform share-token removal.

## [1.21.0] - 2026-06-16

### Fixed
- **`/clean` now expands short links before cleaning** — previously `/clean bit.ly/xyz`
  returned the short URL unchanged because `bit.ly` has no tracking params and the
  expansion step was never reached. A new `clean_url_expanded` async helper mirrors
  `fix_url`'s short-link expansion (and Amazon ASIN extraction) so `/clean` on any
  shortener produces the expanded, tracking-stripped destination URL.
- **Amazon ASIN regex covers mobile and offer-listing paths** — `gp/aw/d/<ASIN>`
  (Amazon mobile) and `gp/offer-listing/<ASIN>` were not matched by `AMAZON_PATH_RE`
  and fell through to generic tracking strip, leaving the product path with a long
  `/ref=...` suffix. Both patterns are now included and normalise to `/dp/<ASIN>`.

## [1.20.0] - 2026-06-16

### Fixed
- **Amazon ASIN extraction after `amzn.to` expansion** — `amzn.to` short links
  are expanded via HTTP redirect before processing, but the ASIN extraction
  block checked the *original* host (`amzn.to`), which is not in `AMAZON_TLDS`,
  so it silently skipped canonicalization on expanded links. The host is now
  re-evaluated after expansion and ASIN extraction fires correctly on the
  resulting `amazon.*` URL.
- **Amazon canonical URL carries a preview URL** — the ASIN extraction return
  had `None` as the preview value, so Telegram would not generate a link
  preview for cleaned Amazon links. Now returns the canonical `/dp/ASIN` URL
  as the preview, consistent with how other non-platform URL changes work.

## [1.19.0] - 2026-06-16

### Added
- **Generic URL shortener expansion** — `bit.ly`, `tinyurl.com`, `t.ly`, `ow.ly`,
  `is.gd`, `rb.gy`, `buff.ly`, and `goo.gl` are now followed to their destination
  before tracking is stripped or a provider rewrite is applied.
- **Platform short links** — `amzn.to` (Amazon), `maps.app.goo.gl` (Google Maps),
  and `pin.it` (Pinterest) are expanded before processing, alongside the existing
  `vm.tiktok.com`, `redd.it`, `b23.tv`, and `t.co`.
- **Platform-specific tracking removal** — `strip_generic_tracking` is now
  host-aware for Amazon (all country TLDs), eBay, AliExpress, LinkedIn, Pinterest,
  Apple Music (`music.apple.com`), Vimeo, and SoundCloud. Each platform has its
  own set of known tracking/affiliate parameters that are dropped when the URL
  host matches.
- **Amazon canonical URL extraction** — for any `amazon.*` TLD, the bot strips
  the URL down to its canonical `/dp/ASIN` form (e.g.
  `amazon.com/Some-Product/dp/B0ABCDE123/ref=nosim?tag=aff` →
  `amazon.com/dp/B0ABCDE123`), removing all referral, affiliate, and search
  tracking from both the path and query string.

## [1.18.0] - 2026-06-16

### Fixed
- **`youtu.be` no longer expanded over the network** — `youtu.be/<id>` was in
  the short-link set, so the bot followed it with an HTTP request before
  rewriting. From a server IP that redirect can land on a Google CAPTCHA page
  (`google.com/sorry/index?continue=...`), and that garbage URL was reposted
  instead of the video. `youtu.be` is now a pure, deterministic *path* rewrite
  to `youtube.com/watch?v=<id>` — no network call — dropping share/tracking
  params (`?is=`, `?si=`, `?feature=`) while keeping a `t`/`start` timestamp.
  The result is a plain link with no rich preview, matching the existing
  Shorts/Live normalization.

## [1.17.0] - 2026-06-16

### Fixed
- **`seen_recent` memory hard-cap restored** — a refactor in v1.3.0 moved
  in-memory dedup pruning to the hourly `cleanup_db` job, silently removing
  the self-contained size guard. If the job-queue was unavailable or slow,
  `_recent_mem` could grow without bound. A `_RECENT_MEM_HARD_CAP` constant
  (200 000 entries) is now checked on every write; when reached the cache is
  cleared wholesale and the triggering key is reinserted. The guard is O(1)
  per call and only fires far above normal operating size.

## [1.16.0] - 2026-06-15

### Added
- **Coverage for the remaining handlers** — tests for the caption, edited-message,
  and channel-post handlers (the edit handler's rate-limit guard was previously
  untested), plus the important "delete not permitted → reply in place" fallback
  in `handle_message`. 103 tests total; every update handler now has coverage.

## [1.15.0] - 2026-06-15

### Changed
- **Inline mode now also cleans non-platform links** — previously `@bot <link>`
  only returned a result for rewritable platforms and silently skipped anything
  else. It now offers a "🧹 Clean link (tracking removed)" result for YouTube and
  other links whose only change is tracking removal or short-link normalization,
  matching what the bot does in group chats. Added inline-query handler tests.

## [1.14.0] - 2026-06-15

### Added
- **Callback-handler test coverage** — `test_handlers.py` now also covers the 🔁
  cycle-provider button (the historically most fragile feature): editing to the
  next provider from a plain-URL message and from a `text_link` entity (label
  preserved), the unknown-platform alert path, the `test` callback, and the
  admin-only gate on `/menu` callbacks. 96 tests total.

## [1.13.0] - 2026-06-15

### Added
- **Handler test coverage** — a new `test_handlers.py` exercises the async update
  handlers with lightweight fakes (no real Telegram): the link-rewrite happy
  path, unsupported-link no-op, muted-user deletion, public/admin command
  routing (including the admin permission gate), repeated-text dedup, duplicate-
  update skipping, and rate-limit enforcement. The handlers previously had zero
  tests. CI now runs the full suite (`pytest -q`, 91 tests) instead of only the
  pure-function file.

## [1.12.0] - 2026-06-15

### Fixed
- **HTML escaping of URLs in reposts** — reposts and the 🔁 cycle button render
  with `parse_mode=HTML` but interpolated the link URL into `href="..."` without
  escaping. A URL with `&` (query params) produced raw ampersands that could
  break Telegram's entity parsing (failing the send and dropping formatting),
  and a `"` could close the attribute. URLs are now `_html.escape(...)`-d for
  both the href attribute and bare-URL text paths.

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
