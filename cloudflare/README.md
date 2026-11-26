# KkInstafix on Cloudflare

The Telegram bot runs as a small JavaScript module Worker with D1 persistence.
The existing Python implementation is retained for rollback. No paid Workers,
Containers, R2, or external database subscription is enabled by this deployment.

## Current deployment

- Worker: `kkinstafix`
- Base URL: https://kkinstafix.legend-mysterio.workers.dev
- Webhook: `/webhook`
- Public liveness and build: `GET /health`. Authenticated readiness: `POST /admin/status`.
- D1: `kkinstafix` (`645ac61c-40da-4846-b1ba-d9461abb579e`), Western Europe
- Compatibility date: `2026-11-15`
- Hourly cleanup and provider checks: `17 * * * *` UTC

## Activation

Open the private setup link supplied in the conversation, paste the **existing**
bot token from BotFather (or the old Railway `BOT_TOKEN` variable), and activate.
Do not create a new Telegram bot: existing group memberships belong to the old
bot identity. Activation verifies the token with `getMe`, encrypts it using
AES-GCM, then sets an authenticated webhook without discarding pending updates.
The one-time setup closes on success. The token never belongs in Git.

The setup link uses a separate key whose SHA-256 digest is stored in
`SETUP_HASH`. An initial Worker also needs `CONFIG_KEY` (the hex-encoded 32-byte
encryption key), `ADMIN_HASH` (the SHA-256 digest of the admin Bearer key),
`WEBHOOK_SECRET` and `RELEASE_CHAT_ID` as secret bindings. Set `WEBHOOK_URL` to
the target URL and bind the D1 database as `DB`. Use a distinct admin key on each
target and preserve `CONFIG_KEY` so the encrypted Telegram token remains
readable. Once activated, regular version uploads inherit the operational
secrets and omit the setup credential.

If Railway restarts, stop its old bot service so it cannot replace the webhook or
restart polling. Leaving a stopped Railway project alone is sufficient; no
Railway resources are deleted by this migration.

## Diagnostics

`POST /admin/status` requires the admin Bearer key. It reports the active build,
sanitized Telegram webhook status, and bot capabilities. Public liveness
reports version and build without querying D1. Setup and provider administration
return an explicit error when paused by the D1 allowance.

## Fixes in 2.4.1

Supported links marked as Telegram URL entities can be pasted without `https://`.
`/clean` and `/preview` ask you to split messages with more than eight distinct
links. Duplicate checks compare cleaned URLs and keep functional values such as
Instagram carousel positions and YouTube timestamps.

The sender attribution link follows the selected preview on multi-link posts.
If `/repair` cannot verify an alternative, try again after the 30-second cooldown
to continue through the provider list. Each attempt still checks up to three
providers.

## Features in 2.4.0

- Reply to a recent fixed post with `/repair` to try up to three configured preview backends. Each check reads at most 8 KiB of metadata and follows at most one same-host HTTPS redirect (at most six fetches total). A success edits the existing post using the durable operation journal. The current backend is excluded from alternative checks; sole-provider posts explain how to use `/refresh` instead. Inconclusive checks keep the current post; a blocked response is not a global provider failure. Checks run only on request, with a 30-second cooldown per user/chat. No media is downloaded. Metadata does not guarantee Telegram playback.
- Inline mode offers the default preview for each link first, then alternative providers, up to 24 choices. Each selection retains the full message and all cleaned destinations. It does not probe providers while typing. Browser-only aliases are not duplicated as preview choices.
- `/music <track or album URL>` (or reply to one) builds a Songlink/Albumlink redirect. An extra universal music result is available inline; ordinary Spotify rewriting is unchanged. Supported input services: Spotify (including its share hosts), Apple Music, YouTube Music, Tidal, Deezer, SoundCloud, Pandora and Amazon Music. Artist pages and Spotify playlists are excluded. There is no Worker API lookup, API key, subscription or music download. Resolution and service availability depend on Songlink; not every catalogue item is supported.
- `/appearance attribution off|on` and `/appearance preview compact|large` affect only the sender’s future posts. `/appearance reset` removes their overrides. Set defaults in a private chat; group settings override those defaults in that group. Inline mode uses private defaults. Layout is stored with each post, so someone else’s retry preserves it. Telegram may ignore media-size hints for some content. No redundant Instagram button is added.
- `/status` and `/config` show remaining conservative bot request/read/write allowances, storage headroom and the next midnight UTC daily reset. Storage has no daily reset. These are bot ledger estimates, not account-wide Cloudflare usage or a billing cap. During a normal pause, authenticated status commands can use bounded inspection headroom (until 10,100 counted operations or the maintenance read/write thresholds); other updates stay paused. Status requests longer than 8 KiB do not use this exception. Administrative status remains available as before.
- FurTrack `/p/<photo-id>` posts use `furtrack.owo.lgbt` for previews and keep a cleaned official clickable URL. Profiles and other paths stay native. The proxy returned photo metadata for two public posts. Imgur’s candidate returned generic download pages in our samples, so it remains disabled. See [provider review](PROVIDER_REVIEW.md#provider-expansion-and-music-240) and [verification observations](provider-expansion-2.4.0.json).

These features reuse existing D1 tables and per-invocation guards. Repair adds no background polling, inline alternatives add no provider requests, and music sharing builds redirect links locally. The feature commands are specific to the Cloudflare runtime; the Python rollback runtime shares the provider catalogue and photo-path restriction.

## Free-tier safeguards in 2.3.1

Cloudflare's documented Free allowances (checked 15 November 2026) include 100,000
Worker requests/day, 10 ms CPU per invocation, 50 external subrequests/invocation,
50 D1 statements/invocation, 5 million D1 rows read/day, 100,000 D1 rows written/day,
500 MB per D1 database and 5 GB total D1 storage. These are account/plan limits,
not a separate entitlement per bot. Workers Logs currently include 200,000 events
per day on Free. Re-check pricing/limits before future deployment changes.

- [Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
- [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/)
- [D1 limits](https://developers.cloudflare.com/d1/platform/limits/)
- [Workers Logs pricing](https://developers.cloudflare.com/workers/platform/pricing/#workers-logs)

The bot adds lower **application safety allowances**, not an account-wide billing
cap: 10,000 protected operations/day, 2 million measured rows read/day, 25,000
measured rows written/day, and a 200 MiB observed database-size threshold. At a
threshold, new POST processing is acknowledged with a paused result without
reposting/deleting originals. Skipped updates are not queued for later delivery;
users must resend after the allowance resets at midnight UTC. Protected status
remains available to inspect the reason. Maintenance has separate headroom up to
3 million reads and 50,000 writes, allowing cleanup while normal work is paused.

A D1-backed UTC ledger records returned row metadata, including index costs and
conservative accounting overhead. It is a soft guard checked before each
invocation; an in-flight operation can cross its threshold slightly. Requests to
public/unauthenticated endpoints, external administrative queries, other Workers,
and other databases are outside that ledger. Account-wide usage must still be
checked through Cloudflare analytics. Incoming traffic still counts toward the
platform request allowance even when processing is paused. The bot cannot promise
that a busy or attacked account never reaches a platform quota.

Every invocation separately meters at most 45 D1 statement slots (batch members
count individually), leaving accounting headroom below 50, at most 24 outgoing
fetch calls and 16 optional Cache API operations. Four short-link expansions run
concurrently, leaving room below the six-connection ceiling. Backup restores
validate the file and estimate the required row writes before applying a single
transaction. Webhook and admin POST requests authenticate before reaching D1.

Cloudflare enforces the Free plan’s built-in 10 ms CPU limit. Custom CPU limits
are a Paid feature: the deployment API rejected that setting and explicitly
confirmed this account is on Free. Release metadata therefore omits custom limits
and rejects attempts to configure them or a legacy usage model. Cloudflare enforces runtime
CPU limits, with its documented burst flexibility; local tests cannot prove all
production invocations consume less than 10 ms. Duplicate HTML rendering was
removed. Probe heads are limited to 8 KiB; truncated heads without useful metadata
are inconclusive, never evidence of a broken provider. Each hourly production
batch now checks two backends, reducing background work. Logs sample 10% of
invocations; trace sampling stays at zero to protect Telegram token URLs.

Retention cleanup deletes at most 250 expired rows per table per hourly run to
avoid write spikes. Recovery records use their original post timestamp for
indexed expiry. Large backlogs may need several cleanup runs. Storage accounting uses D1’s returned size metadata; unsupported page-count
PRAGMAs are not used. The observed storage size carries over at midnight, unlike
daily read/write allowances. Allocated database size may not shrink immediately
after deletes, so reaching the conservative storage threshold can require owner
maintenance before normal processing resumes. No media processing,
AI, Containers, KV, R2, paid storage or new paid subscription is enabled.

Before deployment apply `migrations/0005-free-budget.sql`, which adds the small
usage ledger. Clean installs include it. `/admin/status` returns `free_tier`
with the ledger snapshot and configured safety allowances. Aggregate Cloudflare
analytics—not the application ledger—are authoritative for account usage.

The connected account allowed analytics/resource reads but denied billing
subscription and spend-policy reads during this audit. Independently, Cloudflare’s
deployment API explicitly confirmed the Free plan with error 100328 when a custom
CPU cap was attempted. That failed upload did not change the live Worker or plan.
The setting was removed; the platform retains its own Free CPU limit. On Free,
hitting platform quotas stops service rather than automatically upgrading the
plan. No billing changes were made. `usage_model: standard` alone is not proof of
a Free account; the confirmation above is dated 15 November 2026.
Workers spending policies are not a zero-cost guarantee: their minimum is above
zero, they exclude subscription fees and enforcement can lag.

## Reliability, performance and UX in 2.3.0

The single Retry button now shows its active backend and position, for example
`↻ Retry · EE · 2/8`. Cycling remains continuous. Successful edits have a one-second
per-post cooldown to absorb rapid taps; pending work remains serialized. Muted
users cannot use retry, selection, test or menu callbacks. Notifications report
success only after Telegram and the state commit succeed, and rejected edits
receive a failure explanation. Historical retries also confirm edits first.

Reply to a fixed post with `/refresh` to request the same provider again. A stable
per-operation `_kk_refresh` value is added only to the fetched preview URL, never
to the clean clickable destination or undo data. This attempts another crawl;
Telegram or a provider may still reuse its own cache. Spoiler links cannot be
refreshed into a visible preview. There is no additional URL button.

Preview/source edits first save the complete intended state in `post_operations`.
On success a D1 batch commits controls, the original/undo snapshot, legacy
metadata and the operation receipt together. If storage fails after a Telegram
edit, webhook replay applies the same desired message instead of choosing another
provider. Ambiguous edit timeouts are safely replayed because edits are
idempotent; sends retain the existing no-blind-retry policy. Repeated callbacks
with a completed receipt do not edit again. Confirmed Telegram rejection marks
that operation failed and keeps the previous state. Source edits never send a
second replacement post. Pending reconciliation is attempted before another post
action. Completed receipts store only minimal provider information, and recovery
records expire with their post's seven-day retention window.

Settings now use four SQL queries in one batch instead of seven. Plain messages
and most commands skip provider-health reads. Retry reads health directly rather
than reloading all preferences. Provider health is cached regionally for thirty
seconds and invalidated locally by background checks; mute and user preferences
remain live D1 reads. Cache failures fall back to D1/network behaviour.

Successful known-short-link expansion is cached for five minutes using hashed
keys and an 8 KiB entry-size bound. Access blocks, timeouts and unchanged failures
are not cached. There is no arbitrary-site probing or global mutable request
cache. Cache API entries are regional and may be evicted sooner. Each URL still
has at most four redirect requests, with sixteen expansion requests shared across
one message to leave room for other Worker operations. Extremely long chains
can therefore remain partially expanded.

Formatting fallback first tries native entities with the existing valid keyboard
and preview settings. Only later fallbacks remove the keyboard; spoiler preview
suppression is retained throughout. Oversized source edits receive a short,
rate-limited explanation without quoting their URLs, and leave the original and
existing repost intact.

`/menu` shows six friendly platform choices per page with navigation. Provider
choices include the provider key and hostname so unfamiliar abbreviations are
clear. Old menu callbacks remain supported.

Plain-text spam deletion is off for new chats in both runtimes. The Worker
explicitly inserts that default when creating settings in an existing D1 schema.
Existing saved chat/user choices are preserved; admins can use `/textspam off` to
disable it in an existing chat, or `/textspam on` to opt in. Link, sticker and GIF
deduplication retain their previous behaviour.

Before uploading 2.3.0, apply `migrations/0004-edit-recovery.sql` after earlier
migrations. It adds recovery receipts and tap activity without modifying existing
chat data. Clean installs use the regenerated schema. Configuration exports
exclude message content, operation journals and cache entries.

## Continuous retries in 2.2.2

Retry preview starts another provider cycle after exhausting a round, including
posts already marked exhausted by earlier versions. Temporarily quarantined
backends remain skipped. Browser aliases are not selected as preview backends,
so cycling cannot change an official destination to XCancel or Redlib. Explicit
browser choices still keep their destination. If every backend is temporarily
quarantined, the bot explains that and the button remains usable later. No
migration is required.

## Reddit cleanup fix in 2.2.1

Reddit's `share_id` attribution parameter is removed, case-insensitively, from
Reddit and its configured preview-provider URLs. Comment paths, `context`, `sort`,
`depth` and fragments remain intact. Other sites' `share_id` values are preserved.
The rule applies to official clickable destinations, proxy previews, captions,
inline results and `/clean`. Retry also re-cleans stored post targets from older
versions, accepting their old URL fingerprint and retaining retry history even
when no unused provider remains. Original undo snapshots remain unchanged.
No database migration is required for this patch.

## Improvements in 2.2.0

New reposts remember each tried preview backend for seven days. Retry chooses an
unused, non-quarantined backend; aliases sharing a backend count as the same
attempt. Since 2.2.2, completing a round starts a new cycle on the next click.
Historical buttons without post-control records retain their legacy behaviour.
Explicit browser frontend choices keep their clickable destination during retries.

Multi-link reposts show numbered preview choices with the active choice marked.
Only the original sender or a chat admin can change that selection; anyone can
request a preview retry. Unchanged ordinary URLs can also be selected. Choosing a
preview retains the complete cleaned message and its formatting. Inline mode
shows one result per candidate, each retaining the full surrounding text and all
links. Spoiler links suppress all preview controls.

When Telegram sends an edit for a surviving original (including captions and
channel posts), the existing bot repost is edited, its undo snapshot is refreshed,
and no extra rewrite count, posting quota or duplicate reservation is added.
Deleted originals cannot be edited in Telegram. Unknown/historical originals use
the ordinary rewrite path. Older edit timestamps are ignored. Source mappings,
retry history and controls expire seven days after the initial repost and are not
included in settings exports. An oversized edit keeps the existing repost and
original; a rejected edit never creates a duplicate replacement.

Per-post leases serialize clicks and edits, and stale preview selectors are
rejected. `/status` checks bot membership, group-message visibility, send rights,
preview permissions and deletion rights, with Telegram/BotFather instructions.
Unavailable permissions are reported as unknown; permissions do not guarantee
that an external preview will render or play.

Before upgrading, apply the additive `migrations/0003-post-controls.sql` after
`0002-improvements.sql`, then upload the built Worker. Fresh installs use
`schema.sql`, which includes both migrations.

### Release checks and rollback

CI checks documentation and provider audit changes against the PR base or
previous push commit. It verifies generated configuration, rehearses the
migration contract locally, and runs the Worker and Python suites.

The manual **Release Cloudflare Worker** workflow takes a comparison base SHA.
It builds once and deploys that artifact to the `staging` environment. Select
**promote** on `main` to deploy the same artifact to `production` after staging
passes. In GitHub's production environment settings, restrict deployment
branches to `main` and protect that branch with required checks. Keep production
credentials exclusively in the production environment.

Before the first release, provision and activate an independent staging Worker,
D1 database and Telegram bot. Set the staging environment variable
`KKINSTAFIX_STAGING_CONFIG` to a JSON object with the same deployment fields as
`deployment.json`, including the production compatibility date. Configure each
environment's `CLOUDFLARE_API_TOKEN` with scoped Worker and D1 permissions, and set
`KKINSTAFIX_ADMIN_KEY` to the Bearer key corresponding to that Worker's
`ADMIN_HASH`. For a baseline Worker that still authenticates with the setup key,
temporarily add `KKINSTAFIX_LEGACY_ADMIN_KEY` for preflight and rollback.
Provision the `RELEASE_CHAT_ID` secret with a chat the corresponding bot can
read and reply to. Keep sampled Worker traces disabled.

The script checks cron, indexes and table shape before deploying. It records
migration names and checksums in D1. Migration
`0006-restore-and-release-safety.sql` adds the chat index and two receipt tables,
with no data backfill. Upload and activation use distinct Cloudflare API calls.
When each workflow job prints a one-time `/releasecheck` command, send it as a
human user from that target's configured Telegram chat. The job waits for the
expected build to deliver a reply, then confirms a receipt through admin status.
If verification fails, rollback requires both the recorded deployment and
version IDs to match the active deployment. Additive D1 migrations remain
applied. Rollback artifacts retain deployment metadata for seven days.

For a local dry run with no network requests:

```bash
npm run build --prefix cloudflare
python tools/release_cloudflare.py --dry-run
```

For a verified manual restore using a downloaded release artifact and the same
environment credentials:

```bash
python tools/release_cloudflare.py --rollback release-rollback.json
```

## Improvements in 2.1.0

Messages and captions retain Telegram formatting, including bold, italics,
spoilers, code, quotes and linked labels. If HTML is rejected, delivery retries
with native entities. Spoiler links disable previews and retry buttons to avoid
revealing the hidden destination; oversized spoiler posts keep their original
and receive an explanation. Confirmed replacements are saved before a text
original is deleted, so a storage failure preserves the original.

Inline mode retains surrounding text and all links, up to eight, with an explicit
explanation for queries exceeding the link or Telegram message limit.

`/diagnose <url>` or `/diagnose` as a reply reports cleaned destinations, preview
URLs, provider health, removed parameter names and likely skip reasons. It does
not consume rate-limit or deduplication reservations. All query values and URL
credentials are masked in its report. A fixed-post reply uses the stored original
and its author's preferences where available.

`/undo` as a reply restores the full original text with entities for new records,
or a supported single photo, video, animation, document, audio or voice attachment
using Telegram's file ID, with its original caption and entities. This creates a
bot-authored copy, not the original sender's message. Albums are not reconstructed.
Snapshots expire after seven days and are excluded from configuration exports.
Historical records without a snapshot explicitly fall back to the original URL.

### Upgrade an existing D1 database

Before deploying 2.1.0, apply `migrations/0002-improvements.sql` through D1's query
API or Wrangler. It is additive and safe to run again. Clean installs use the
regenerated `schema.sql`, which includes the migration. Preserve the existing
secret bindings and bot token when uploading the rebuilt Worker.

### Background provider monitoring

The existing hourly cron checks four rotating preview backends using fixed public
samples, never user-submitted links. Only repeated failures on two curated posts,
corroborated by another backend succeeding on both, count toward quarantine.
Three confirmed checks temporarily skip that backend for six hours; successful
content checks clear the failure history. HTTP 403/429, timeouts and profile-only
observations cannot quarantine a provider. Stale cached decisions expire.
Monitoring does not establish that every Telegram client can play a preview.
Native previews and browser frontends are not probed as proxy backends.

`POST /admin/check-providers`, authenticated with the same private Bearer key as
`/admin/status`, runs one bounded batch. The hourly lease prevents duplicate
checks. `/admin/status` includes aggregate cached health counts and timestamps.
Only fixed evidence labels, HTTP status and timestamps are stored for probes.

## Preserve old settings

The new D1 schema is compatible with the bot's SQLite tables. The live Railway
SQLite file was not available during this migration. No test database is imported.
Without an old export, chat preferences start at defaults; opt-outs issued after
activation are durable in D1.

For each chat, an admin can restore an existing `/export` JSON backup up to
64 KiB using `/import` in the same chat. A complete export replaces the saved
provider selections, platform overrides, mutes, opt-outs and user preferences
in one transaction. Partial JSON files merge their entries with current settings.
Each restore reserves its estimated D1 writes before it changes any settings.
A committed receipt lets Telegram retry confirmation without replaying the
restore. If the remaining daily allowance cannot cover the restore, try again
after midnight UTC. For a complete Railway `bot_data.sqlite3` backup:

```bash
python cloudflare/migrate-sqlite.py /path/to/real/bot_data.sqlite3 /tmp/kkinstafix-migration.sql
```

Review and apply the SQL to the existing D1 database via its authenticated query
API before activation. The exporter opens the source database read-only and only
copies the established chat/settings/statistics tables. It never copies runtime
credentials. Keep SQL containing user/chat data out of Git.

## Build and tests

```bash
python cloudflare/generate-config.py
npm ci --prefix cloudflare
npm run build --prefix cloudflare
npm test --prefix cloudflare
```

`generate-config.py` extracts provider/tracking data and the SQLite schema from
the Python source without executing the bot. Provider mappings follow the shared catalogue; the latest changes and probe
limitations are documented in [PROVIDER_REVIEW.md](PROVIDER_REVIEW.md). Platform probes no longer block delivery or mistake a 403 on a
post for a failed embed: the selected provider is posted immediately, with an
alternative-provider button. With `/fallback on`, cached background health can
temporarily skip a confirmed failing preview backend without changing the saved
provider choice. If all backends are quarantined, the original URL supplies the
preview. `/fallback off` keeps the selected backend. No provider health
requests block a user message.

Tests use Miniflare/workerd with a real local D1 database and a mocked Telegram
API. The installed workerd binary supports compatibility dates through
`2026-08-06`; tests pin that supported date. Staging uses the production compatibility date and exercises authenticated
Telegram delivery before production promotion.

Delivery confirms `sendMessage` before deleting text originals. Captions, edited
messages and channel posts keep their original content. Permission failures do
not trigger repeated sends. Network timeouts preserve originals and are not
blindly retried because Telegram may have accepted the first send. Definitive
rate limits return HTTP 503 with Retry-After so Telegram can retry the update.
D1 deduplicates update IDs and link reservations across Worker isolates.

Workers Logs record structured error codes, not tokens or message bodies. Trace
instrumentation is enabled with sampling at zero because Telegram puts the bot
token in its API URL path. No activation key is put in an HTTP URL query string;
the browser consumes it from a URL fragment and clears its history entry.

Free-tier limits still apply. The Worker bounds link expansion to eight URLs per
message and four redirects per URL, with a shared sixteen-request expansion budget. Cleanup
limits delivery history and undo records to seven days. If free quotas are
exceeded, service can stop until they reset; this setup does not upgrade a plan.


### Rewrite delivery fixes (v2.0.2)

Single-link messages retain their surrounding text, including when the provider
button changes the URL. Bare links keep the compact sender label. If adding the
sender or expanding domains would exceed Telegram's message limit, the bot keeps
the original and posts cleaned links in a reply. Instagram share parameters
`dlrf` and `psln` are stripped from original and provider URLs, including `/clean`.
Commands addressed to another bot are ignored; muted users cannot invoke commands.
Imports migrate known retired providers to current defaults and skip the removed
LinkedIn rewrite settings while restoring the remaining settings and opt-outs.


### Linked text and provider targeting (v2.0.3)

The Worker reads both visible URLs and Telegram `text_link` entities in messages
and captions. Replacements preserve clickable labels and other hyperlinks;
plain-text fallbacks include their destinations. Entity offsets remain in UTF-16
units so emoji and leading whitespace do not move the links.

New provider buttons identify their post using a short hash of the cleaned path,
query and fragment, independent of the provider hostname. Older buttons prefer
the recorded original post and decline ambiguous messages rather than editing an
unrelated URL. Oversized URL replies use compact clickable labels while keeping
the original. If Telegram rejects the URL, a short explanatory reply replaces the
previous silent return.


### Official Instagram destinations (v2.0.4)

Instagram message links, linked sender labels, captions, plain fallbacks and
inline results now point to cleaned HTTPS URLs on `instagram.com`. The selected
embed provider is used only in Telegram's `link_preview_options.url`. Provider
switching changes the preview while preserving the official clickable URL.
Existing Instagram provider URLs are converted on repost; older provider buttons
also convert their selected post to the official destination when used. `/clean`
continues to remove tracking without changing hosts, and `/testall` lists preview
URLs so the available providers remain distinguishable. Other platforms keep
their existing click-through behaviour.


### Changing Instagram share tokens (v2.0.5)

Recent share links introduced `xtok` and `vrfl`. Instagram content URLs under
`/p/`, `/reel/`, `/reels/`, `/tv/` and `/stories/` now keep only `img_index` in
the query, so unknown share-token names are removed without requiring another
release. This applies to original and provider hosts, clickable destinations,
proxy previews, `/clean`, inline results and provider switching. Profile URLs
remove the known share parameters without being routed to a post-preview
provider. Other websites retain their functional query parameters. Buttons from
before this sanitisation update can still identify and clean their post.


### Cleaner Instagram message layout (v2.0.6)

Single-post Instagram replacements request a large preview above the message.
Bare links use an italic `Shared by <sender>` attribution linked to the cleaned
official Instagram URL. Messages with surrounding text and captions retain that
content and place attribution underneath it. Sender mode `none` omits attribution.
The inline keyboard places `↗ Instagram` and `↻ Retry preview` on one row; retry
preserves preview placement and the official destination button. Provider titles
and video padding remain controlled by the provider metadata and source media.


### Remove duplicate Instagram action (v2.0.7)

The attribution already links to official Instagram, so the redundant Instagram
URL button is removed. `↻ Retry preview` is the only inline button. Existing
posts adopt this keyboard when their retry button is used; new posts use it
immediately. Preview placement and the linked attribution are unchanged.


### Shared presentation and sanitisation (v2.0.11)

All supported platforms now share the preview-first layout and bottom linked
`Shared by` attribution. The previous renderer had only applied this to Instagram.
Captions, surrounding text, multi-link posts, inline results and retry previews
follow the same placement rules. No duplicate open-site buttons are added.

Normal provider selections use cleaned official-site click-through URLs and
proxy-only previews; deliberately selected no-account browser frontends such as
XCancel and Redlib retain their purpose. Pasted proxy URLs are also recognised,
including Koutube's short hostname. Native YouTube links now receive the common
layout even when no URL rewrite is necessary. Retrying a recorded legacy compact
post upgrades its emoji header to the linked attribution.

Cleanup combines common tracking keys (including any `utm_` key), platform rules
and original-site-specific rules on both original and proxy URLs. YouTube share
analytics are removed while video IDs, playlists, indexes and playback positions
are retained, including during Shorts/short-link canonicalisation. Other required
fields, such as Facebook comment IDs and Xiaohongshu access tokens, remain intact.
See `presentation-cleanup-audit-2026-11-15.json` for coverage of all 22 platforms
and 56 configured options. This audit checks bot behaviour, not fresh availability
or playback of every third-party preview service.


## Release documentation

Before each release, update the root [CHANGELOG.md](../CHANGELOG.md) with the
user-visible changes, fixes and relevant validation. Keep this README aligned
with the final deployed behaviour. For provider changes, also update
[PROVIDER_REVIEW.md](PROVIDER_REVIEW.md) and the corresponding audit evidence;
distinguish metadata checks from verified Telegram playback. Documentation-only
changes do not require a Worker version bump or deployment.
