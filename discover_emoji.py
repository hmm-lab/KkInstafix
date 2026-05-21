"""
Run once to discover custom emoji IDs from Telegram sticker/emoji packs.
Usage:  BOT_TOKEN=your_token python discover_emoji.py
"""
import os
import urllib.request
import urllib.parse
import json

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Set BOT_TOKEN environment variable first.")

PACK_NAMES = [
    "logos_td",        # fullyst.com/en/emoji_set/logos_td
    "appslogos",       # emoji.gg/pack/767129-apps-logos candidates
    "apps_logos",
    "AppLogos",
    "AppIcons",
]

def api(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return json.load(r)
    except Exception as e:
        return {"ok": False, "error": str(e)}

for name in PACK_NAMES:
    res = api("getStickerSet", name=name)
    if not res.get("ok"):
        print(f"  {name}: not found")
        continue

    pack = res["result"]
    print(f"\n{'='*60}")
    print(f"Pack: {pack['name']}  |  Title: {pack['title']}")
    print(f"Type: {pack.get('sticker_type')}  |  Count: {len(pack['stickers'])}")
    print(f"{'='*60}")
    for s in pack["stickers"]:
        eid = s.get("custom_emoji_id") or s.get("file_unique_id")
        emoji = s.get("emoji", "?")
        print(f"  emoji={emoji}  id={eid}")
