# Provider refresh — 15 November 2026

The running Worker and legacy Python bot share the refreshed catalogue through
`generate-config.py`. Working Instagram (`ee`), X (`vx`), TikTok (`tnk`) and
Bluesky (`bskx`) defaults are unchanged.

## Catalogue changes

| Platform | Change | Evidence |
| --- | --- | --- |
| Instagram | Add `uu` and `zz`; remove obsolete `instagramez.com` option | Both additions returned preview metadata on a real reel. The removed domain redirected to an unrelated advertising host. ZZ is documented by its operator. |
| X/Twitter | Correct `ez` to `xeezz.com`; add `twittpr` | EmbedEZ coverage and FxEmbed domain documentation. Twittpr returned a real text-post card. |
| TikTok | Add `kk` and `fix`; correct `ez` to `tiktokez.com`; remove `vx`, `tik`, `tfx`, `proxitok` | KKTikTok returned direct video, FixTikTok and TikTokEZ returned media cards. The fxTikTok maintainer documents the old vx/tik aliases as unmaintained. Other removed entries were obsolete/unavailable aliases. |
| Facebook | Replace obsolete/ad-redirecting `ez` with current `facebed.seria.moe` mapping | Current Embed Fixer catalogue; profile-only test remains inconclusive for actual reels. |
| Threads | Correct `fix` to `fixthreads.seria.moe` | Current maintainer catalogue; keep documented vx alternative despite an inconclusive timeout. |
| Bilibili | Add `ez` at `bilibiliez.com` | Official coverage; real video produced media metadata. |
| Pinterest | Replace unverified `vxtin.com` and `pin.ez` with `pinterestez.com` | Official EmbedEZ coverage; profile/sample response does not prove every pin works. |
| Bluesky | Remove unsupported `vx` and `cbsky` aliases | First returned 404; second unavailable with no current maintainer-backed listing. Existing working alternatives retained. |
| Spotify | Remove `fixspotify.com` alias | Returned 404 for a known live track; working `fxspotify.com` retained. |
| Reddit | Remove stale `libredd` browser frontend; preserve Redlib with its separate vx preview | Frontend returned 404, and it lacked an embed pairing. No default change. |
| LinkedIn | Stop swapping to unverified hosts | Existing `vxtdin.com` / `lnkedin.ez` entries had no verified maintained implementation. Tracking cleanup continues on LinkedIn's original URLs. |

Instagram's `psln` share parameter is now removed alongside its existing tracking
parameters. It is platform-specific and does not affect YouTube timestamps.

## Interpretation and limitations

`provider-audit-2026-11-15.json` records bounded provider-level HTTP observations.
The original probe's `no-media` label is not a failure verdict: direct video/CDN
responses and text-only X posts can be valid without an HTML media tag. A 403,
profile-only 404, timeout, or access-controlled frontend does not by itself prove
a provider is permanently dead. In particular, XCancel/Redlib browser frontends
are retained with a separate vx embed provider. The checker now distinguishes
usable metadata/media from reachability and rejects login/error cards.

No messages were posted to Telegram during provider testing. Providers can still
fail on private, deleted, age-restricted or region-restricted content. Automatic
rewriting does not wait on provider probes. The per-message provider button
remains the fallback when a particular post fails to render.

## Primary sources

- https://embedez.com/coverage
- https://github.com/seriaati/embed-fixer/blob/main/embed_fixer/fixes.py
- https://docs.fxembed.com/deployment/configuration/
- https://github.com/Knoppiix/InstaEmbedRouter
- https://github.com/okdargy/fxTikTok
- https://github.com/FxEmbed/FxEmbed


## Follow-up: kkclip / kk retired (v2.0.8)

Removed `kkclip.com` (`kkclip`) and `kkinstagram.com` (`kk`) from Instagram's
selectable options after user reports of failed Telegram previews. Both returned
HTTP 200 without `og:image` or `og:video` metadata for the public sample post in a
follow-up check; HTTP success alone does not establish a working embed. The
remaining options are `vx`, `ee`, `uu`, and `zz`, with `ee` still the default.
Old domains remain recognised as input aliases only. Stale saved choices and
backups migrate to the current default, and retry buttons use the reduced list.


## Lexedia gist and comment review (v2.0.9)

Reviewed the [gist and linked comment](https://gist.github.com/Lexedia/bbbde4dbbf628b0bfe8476a96a977a8f?permalink_comment_id=6410035),
including all 11 comments, rather than trusting the table's old “Not broken” labels.
The linked comment specifically recommends [Koutube](https://github.com/iGerman00/koutube).
Probe evidence is in `provider-gist-audit-2026-11-15.json`; requests inspect public
post metadata, not actual playback on every Telegram client.

| Candidate | Decision | Evidence |
| --- | --- | --- |
| `koutube.com` / `koutu.be` | Add one `youtube:koutube` option | Both returned the real sample video's title, image and video metadata. The short hostname is the same service, not a second independent fallback. |
| `boobsky.app` | Add `bluesky:boobsky` | Real image and video posts returned the corresponding image/video metadata. |
| `vxbsky.app` | Restore `bluesky:vx` | Fresh image/video post probes succeeded; the earlier removal was based on older inconclusive evidence. |
| `bskyx.app` | Skip | Operator recommends `bskx.app`; the older hostname supports raw media only. |
| `ddinstagram.com` | Skip | Sample returned 503; newer gist comment reports InstaFix dead. |
| `instagramez.com` | Keep retired | Redirected to an unrelated advertising hostname with no embed metadata. |
| `tfxktok.com` | Skip | Sample returned 500. |
| `tiktxk.com` | Skip | Redirected to the original TikTok page; no direct video metadata. `tnktok.com` returned video metadata for the same post. |
| `vxtiktok.com` | Keep retired | Returned a “Notice” card without media; latest gist comment reports a legal takedown. |
| `fixthreads.net` | Skip | Returned 503; upstream repository is archived. Existing alternate Threads deployment also redirected to a login card for the sample, so Threads playback is not verified by this review. |
| `twitterez.com` | Skip | Redirected to the EmbedEZ homepage without post metadata; existing `xeezz.com` option is retained. |

Native YouTube remains the default; enable the optional preview with
`/setprovider youtube koutube`, and restore it with `/setprovider youtube native`.
Clickable YouTube URLs remain official while the selected provider supplies the
preview. Video IDs, playlists and timestamps survive cleanup. The Koutube
operator documents a public cache listing; leave native selected when that is
undesirable. Existing Instagram/TikTok/Bluesky defaults remain unchanged, and
`kkclip` / `kk` remain retired following the user's direct reports.


## Kyrela FIXERS.md review (v2.0.10)

Compared the [current provider list](https://github.com/Kyrela/FixTweetBot/blob/main/FIXERS.md)
with the active catalogue, then checked candidate routes against public posts.
Evidence is in `provider-kyrela-audit-2026-11-15.json`.

| Added Instagram key | Preview host | Observed evidence |
| --- | --- | --- |
| `to` | `toinstagram.com` | Reel and carousel-post routes returned the matching author's media metadata. |
| `embeds` | `ig.embeds.now` | Reel video metadata and carousel image metadata; use one hostname rather than duplicate aliases of Embeds.now. |
| `revived` | `fkinstagram.com` | Reel video and carousel image metadata. The current InstaFix Revived README lists this community deployment instead of the failed `instagram7.com` hostname. |
| `ins` | `ins.so` | Distinct media endpoints for two posts, 404 on a deliberately nonexistent post, and HTTP 200 `video/mp4` for the reel's media endpoint. |

`ee` remains the default. All four additions use official, cleaned Instagram
click-through URLs and the existing single Retry preview button. Old Instagram7
links are recognised as input aliases and converted to the official destination.
Username-prefixed post/reel URLs from the comparison table are now recognised,
and their query parameters use the same sanitisation rules as ordinary posts.

Other results:

- OGInstagram and its gallery hostname returned HTTP 200 HTML without preview
  metadata on both sample content types; not added on that evidence.
- `instagram7.com` returned 503; the maintainer now documents `fkinstagram.com`.
- `ig.mynameistito.com` worked on the reel sample but returned 404 for the
  carousel sample; omitted from the general-purpose rotation for now.
- `xnstagram.com` returned generic product metadata rather than the reel;
  `fxinstagram.com` returned 403, and `onebigram.com` returned 404. These are
  inconclusive for universal availability, so they are not labelled permanently dead.
- `instagramfix.com` duplicated the same Embeds.now service; no duplicate option.
- `mbedfx.app/ig/...` and `fixembed.app/ig/...` returned reel video metadata, but
  require platform path prefixes. They are documented candidates rather than
  incorrectly configured as simple hostname replacements in this update.
- `fzthreads.com` returned 404 on the sample, Facebook returned a login card,
  and the Spotify candidate returned 503; no verified replacements were established.
- The Bluesky viewer produced image metadata but no video metadata for the video
  sample. Existing Bluesky options already cover both tested media types.
- The additional YouTube host returned no metadata and Imgur redirected to an
  EmbedEZ landing page. Neither was added.

These checks establish usable metadata on the sampled public posts, not playback
in every Telegram client, every media size, or every account visibility setting.

## Runtime monitoring (2.1.0)

The catalogue is unchanged in this release. Hourly checks rotate four preview
backends using fixed public samples. Two curated samples must fail while a
control provider succeeds on both before a check counts as a confirmed failure.
Three confirmed checks cause a six-hour skip; successful checks recover the
backend. Profile observations, HTTP 403/429 and timeouts cannot quarantine.
This is conservative sampled evidence, not a live guarantee for every provider
or every post. Saved chat choices remain intact; `/fallback off` disables cached
health-based switching. See [runtime details](README.md#background-provider-monitoring).

## Sanitisation regression corpus (2.2.0)

`test/fixtures/sanitisation.json` supplies representative content-path fixtures
for every configured platform, plus short YouTube URLs/Shorts and changing
Instagram share-token names. These are offline fixtures, not live availability
claims. Tests run each fixture through every configured provider, compare
functional paths and queries, re-clean official URLs, and normalise pasted proxy
URLs. They retain YouTube playlist/index/timestamps and timestamp fragments,
Instagram carousel indexes, Facebook comment IDs, Bilibili part selection and
Xiaohongshu access tokens while removing tracking. No provider is added or removed
in 2.2.0. Per-post retry history also treats browser aliases sharing a preview
backend as one attempt.

## Reddit share attribution regression (2.2.1)

A reported Reddit post URL retained `share_id`. Added a Reddit-scoped rule to the
shared configuration, leaving functional comment-navigation parameters intact.
The fixture corpus now includes that post path and checks every Reddit option.
Runtime tests cover official links, inline output, `/clean`, and cleanup of
already stored targets on retry, including exhausted provider history. This is a
cleanup correction; provider selections and availability claims are unchanged.

## Retry UX and cached health (2.3.0)

No provider mappings changed. Retry displays the active backend and position,
continues cycling, and preserves explicit browser destinations. Cached background
health expires after thirty seconds; it remains sampled evidence rather than a
playback guarantee. `/refresh` changes only the selected preview request URL and
does not claim to force Telegram to regenerate its cache. User opt-outs/mutes and
other preferences are not cached. See the runtime README for recovery semantics.

## Free-tier probe bounds (2.3.1)

Production checks now rotate two backends per hourly batch rather than four.
Metadata prefix reads stop at 8 KiB; if that prefix is truncated and contains no
usable metadata, the result is uncertain rather than a failure. This preserves
conservative quarantine rules while reducing CPU/network work. No catalogue
mapping or default changed.

## Provider expansion and music (2.4.0)

The catalogue now has 23 platforms / 57 options. Added FurTrack `fix` →
`furtrack.owo.lgbt` for `/p/<numeric photo ID>` only. Two real posts returned HTTP
200 with distinct titles, photographer attribution and `og:image` URLs on
FurTrack’s own image host. This is metadata evidence, not proof of playback or
long-term availability. Invalid `/p/1` returned “Post not found”, which the checker
now rejects. Other FurTrack paths stay native. The hourly rotating health check
uses a single observation sample and does not quarantine this sole backend.

Candidate Imgur `imgurez.com` was not added: the single-image example and a gallery
redirected to `embedez.com/download`, with generic/missing metadata. This observation
does not prove the service is permanently broken; a valid working post is needed
before enabling it. Native Imgur links continue receiving generic tracking cleanup.

Songlink and Albumlink encoded redirect URLs were verified using Spotify track
`4PTG3Z6ehGkBFwjybzWkR8` and album `4C4LvbYS0pxXLW5sGD9EK5` respectively. The
returned titles matched the requested song/album. This implementation deliberately
uses redirects rather than the music API. No new automatic music rewrite default
is introduced. Input validation accepts supported service content paths only;
Spotify short share hosts are passed to Songlink for resolution, without Worker
fetches. See `provider-expansion-2.4.0.json` for exact public test URLs and limitations.

Primary references: [FurTrack photo](https://www.furtrack.com/p/826598),
[FurTrack proxy](https://furtrack.owo.lgbt/p/826598),
[EmbedEZ coverage](https://embedez.com/coverage),
[Songlink redirect documentation](https://github.com/kweiberth/songlink-docs),
and [Songlink/Odesli](https://odesli.co/). The comparison bot’s
[configuration](https://github.com/campfred/tg-previewsynth-bot) supplied candidate
hosts; provider responses, rather than its list alone, determined activation.


## Provider fallback and rechecks in 2.4.1

Automatic fallback, legacy retries and manual repairs share the same candidate
filter. Browser-only aliases cannot act as preview backends. Retry and repair
exclude the active backend, preserve deliberately selected browser destinations,
and keep the existing preview when no alternative qualifies. Automatic fallback
uses the original URL when every backend is quarantined. An explicit
`/fallback off` still keeps the selected backend.

New public content samples let X and TikTok meet the existing two-sample
corroboration requirement. One slot in a two-provider hourly batch can recheck a
quarantined provider after three hours. The other slot advances the usual
rotation. The added samples are covered by mocked probe tests. Availability
depends on what the providers return when the scheduled check runs.

## Instagram provider refresh — 26 November 2026

Checks used the Telegram crawler user agent on the reported reel
`DgKDChjK7IP`, the existing public reel and carousel samples, and a recent reel
and photo. Missing-post controls checked whether providers returned error cards.

| Provider | Result and decision |
| --- | --- |
| `ig.embeds.now` | Returned video metadata on all three reels and image metadata on the carousel and photo. Moved to the default. |
| `uuinstagram.com` and `toinstagram.com` | Returned video or image metadata for all five public samples. Placed first in Retry after the default. |
| `zzinstagram.com` | Returned video metadata for all three reels and redirected the carousel and photo to images. Retained. |
| `fxig.seria.moe` | Returned video metadata for the reported reel and the existing reel and carousel samples. The recent reel returned 404 and the photo request timed out. Replaces `vxinstagram.com`, which returned 404 on every sample. |
| `ins.so` | Returned media metadata for the reported reel, existing samples and photo. The recent reel returned 404. Retained as the last alternative. |
| `eeinstagram.com` | Returned an HTTP 200 “Post not found” card for all three reels and media for the carousel and photo. Retired from preview selection. |
| `fkinstagram.com` | Returned HTTP 503 on every sample. Retired from preview selection. |

The old provider domains are accepted as pasted links. Stored choices for
retired providers fall back to the new default. The checks verified response
metadata and direct image responses. Telegram playback depends on its crawler
and client. This update adds no per-message probes or D1 migrations.
