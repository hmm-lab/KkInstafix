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
