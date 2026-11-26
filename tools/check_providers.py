#!/usr/bin/env python3
"""Provider health checker for KkInstafix.

Builds a fixed URL for every provider host (using the same logic the bot uses)
and reports reachability separately from evidence of a usable embed.
Profile/landing samples are inconclusive; use a real post to test media.
A successful content test does not guarantee every post will embed.

IMPORTANT: run this from a host with open outbound network access. Sandboxed
environments with an egress allowlist (e.g. Claude Code on the web) will return
a uniform proxy error for every host, which is meaningless — see the README.

Usage:
    python tools/check_providers.py                 # check everything
    python tools/check_providers.py --platform twitter
    python tools/check_providers.py --json
    python tools/check_providers.py --timeout 15

Exit code is the number of DOWN hosts (0 = all reachable), so it can gate CI.
"""
import argparse
import concurrent.futures as cf
import json
import os
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse, urlunparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BOT_TOKEN", "health-check-not-used")

import bot  # noqa: E402

# Telegram's real preview-crawler UA — embed providers whitelist this, so it is
# the closest thing to "what Telegram sees" when it generates a preview.
UA = "TelegramBot (like TwitterBot)"


def build_check_urls(platform_filter=None):
    """Yield (platform, key, host, url, is_default) for every provider host.

    Reuses bot.SAMPLE_URLS + bot.apply_provider so this never drifts from the
    bot's own rewriting logic. A platform with no sample URL is skipped (the
    test suite guards against that happening accidentally).
    """
    for platform, cfg in bot.PROVIDERS.items():
        if platform_filter and platform != platform_filter:
            continue
        base = bot.SAMPLE_URLS.get(platform)
        if not base:
            continue
        for key in cfg["options"]:
            url = bot.apply_provider(base, platform, key)
            yield platform, key, cfg["options"][key], url, cfg["default"] == key


class _Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property", attrs.get("name", "")).lower()
            self.values[key] = attrs.get("content", "")


def has_usable_embed(body, content_type="text/html"):
    """Recognize real metadata/media, excluding error and login cards."""
    if content_type.startswith(("image/", "video/", "audio/")):
        return True
    parser = _Metadata()
    parser.feed(body)
    values = parser.values
    title = (values.get("og:title") or values.get("twitter:title") or "").strip().lower()
    description = (values.get("og:description") or values.get("twitter:description") or "").strip().lower()
    if title in {"fix instagram embeds", "furtrack"} and description.startswith("post not found"):
        return False
    if title == "embeds.now" and description.replace("’", "'").startswith((
        "sorry, this link couldn't be loaded", "this doesn't exist anymore, is private",
    )):
        return False
    if any(error in title for error in (
        "log in", "login", "something went wrong", "not found", "unavailable",
        "access denied", "notice", "unknown", "embed failed", "failed to get post",
    )):
        return False
    return bool(title and any(values.get(k) for k in (
        "og:image", "og:video", "og:video:url", "og:description",
        "twitter:image", "twitter:player", "twitter:description",
    ))) or bool(values.get("og:video") or values.get("og:video:url"))


def check(url, timeout):
    """Return reachability and separate embed evidence; 403 is never EMBED."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            content_type = resp.headers.get("Content-Type", "text/html").lower()
            body = resp.read(131072).decode("utf-8", "ignore")
            final_host = urlparse(resp.url).hostname
        has_embed = has_usable_embed(body, content_type)
        note = "direct-media" if content_type.startswith(("image/", "video/", "audio/")) else ""
        if final_host != urlparse(url).hostname:
            note = f"redirect:{final_host}"
        return code, int((time.time() - t0) * 1000), has_embed, note
    except urllib.error.HTTPError as e:
        return e.code, int((time.time() - t0) * 1000), False, "http-error"
    except Exception as e:
        return None, int((time.time() - t0) * 1000), False, type(e).__name__


def is_up(code):
    return code is not None and 200 <= code < 500


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check KkInstafix provider hosts.")
    ap.add_argument("--platform", help="only check this platform")
    ap.add_argument("--timeout", type=float, default=10.0, help="per-request timeout (s)")
    ap.add_argument("--workers", type=int, default=12, help="parallel requests")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args(argv)

    if args.platform and args.platform not in bot.PROVIDERS:
        ap.error(f"unknown platform '{args.platform}'. Valid: {', '.join(sorted(bot.PROVIDERS))}")

    jobs = list(build_check_urls(args.platform))
    if not jobs:
        ap.error("no provider hosts to check")

    results = {}
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(check, j[3], args.timeout): j for j in jobs}
        for f in cf.as_completed(futs):
            platform, key, host, url, is_default = futs[f]
            results[(platform, key)] = (host, url, is_default, f.result())

    rows = []
    up = down = 0
    for platform, key, host, url, is_default in jobs:
        host, url, is_default, (code, dt, embed, note) = results[(platform, key)]
        good = is_up(code)
        up += good
        down += not good
        rows.append({
            "platform": platform, "key": key, "host": host, "default": is_default,
            "code": code, "latency_ms": dt, "has_embed": embed,
            "status": "EMBED" if good and embed else "REACHABLE" if good else "UNREACHABLE", "note": note,
        })

    if args.json:
        print(json.dumps({"summary": {"up": up, "down": down, "total": up + down},
                          "results": rows}, indent=2))
    else:
        print(f"{'platform':<12} {'key':<10} {'host':<32} {'code':<6} {'ms':<6} {'embed':<6} {'status'}")
        print("-" * 92)
        for r in rows:
            star = " *" if r["default"] else "  "
            print(f"{r['platform']:<12}{star}{r['key']:<10} {r['host']:<32} "
                  f"{str(r['code']):<6} {r['latency_ms']:<6} "
                  f"{'yes' if r['has_embed'] else 'no':<6} {r['status']} {r['note']}")
        print("-" * 92)
        print(f"UP: {up}   DOWN: {down}   total: {up + down}")
        if down and all(r["code"] in (403, 407, 502) for r in rows):
            print("\n⚠️  Every host returned the same proxy-style error — you are probably\n"
                  "    behind an egress allowlist. Run this from a host with open network.")

    return down


if __name__ == "__main__":
    sys.exit(main())
