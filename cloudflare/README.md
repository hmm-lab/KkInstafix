# KkInstafix on Cloudflare

The Telegram bot runs as a small JavaScript module Worker with D1 persistence.
The existing Python implementation is retained for rollback. No paid Workers,
Containers, R2, or external database subscription is enabled by this deployment.

## Current deployment

- Worker: `kkinstafix`
- Base URL: https://kkinstafix.legend-mysterio.workers.dev
- Webhook: `/webhook`
- Readiness: `/health` (`active` stays false until Telegram activation)
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

`CONFIG_KEY`, `SETUP_HASH` and `WEBHOOK_SECRET` are Worker secret bindings.
`WEBHOOK_URL` is a non-secret binding; `DB` is the D1 binding. Re-deployments must
inherit these three secret bindings. Replacing `CONFIG_KEY` without re-encrypting
the stored bot token will make the token unreadable.

If Railway restarts, stop its old bot service so it cannot replace the webhook or
restart polling. Leaving a stopped Railway project alone is sufficient; no
Railway resources are deleted by this migration.

## Diagnostics

`POST /admin/status` accepts the private setup key as a Bearer credential and
returns sanitized Telegram webhook status and bot capabilities. It never exposes
the token or encryption key. Activation remains closed after success. Reloading
the setup page detects completed activation and links to the Telegram bot.

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
attempt. Once no alternatives remain, the bot explains this without cycling back.
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

`tools/check_release.py --base HEAD^` verifies the single Worker version in source,
the README files and dated changelog; runtime changes require documentation, and
provider changes require audit notes. It also verifies generated configuration
and schema. CI runs it alongside the Worker suite and Python 3.11/3.12 suites.
The sanitisation fixture corpus covers all 22 platforms and checks every provider
option, pasted proxy paths, idempotent cleaning and functional parameters.

`.github/workflows/release.yml` is a manual release workflow that runs all checks,
builds, applies additive migrations, inherits existing secrets, verifies active
readiness/version and the Telegram webhook, and restores the previous Worker if
post-upload verification fails. It serializes releases and refuses rollback over
a newer deployment. D1 migrations are retained during code rollback. Failed or
ambiguous uploads are not blindly repeated.

To enable unattended releases, place the workflow on GitHub's default branch and
configure the `production` environment with `CLOUDFLARE_API_TOKEN` (Workers Scripts
edit and D1 edit for this account) and `KKINSTAFIX_ADMIN_KEY` (the existing private
admin key). Credentials are not committed or retrieved from the connector. This
repository update does not create those secrets. Trigger **Release Cloudflare
Worker** from Actions once configured. The rollback artifact is retained seven
days and contains only deployment/version metadata.

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

For each chat, an existing `/export` JSON backup can be restored using `/import`
by an admin in the same chat. For a complete Railway `bot_data.sqlite3` backup:

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
provider choice. `/fallback off` keeps the selected backend. No provider health
requests block a user message.

Tests use Miniflare/workerd with a real local D1 database and a mocked Telegram
API. The installed workerd binary supports compatibility dates through
`2026-08-06`; tests pin that supported date. Production uses today's configured
date and its readiness/security endpoints are checked after deployment.

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
message and four redirects per URL, within the Free subrequest budget. Cleanup
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
