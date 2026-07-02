#!/usr/bin/env python3
"""Scrapes typefoundry.directory into foundries.json. Stdlib only."""
import json
import re
import ssl
import time
import urllib.error
import urllib.request

SSL_CTX = ssl.create_default_context()


def _fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (foundry-viewer personal use)"})
    try:
        return urllib.request.urlopen(req, timeout=60, context=SSL_CTX).read()
    except (ssl.SSLError, urllib.error.URLError):
        # Some macOS Python builds reject this site's CA chain; it's a
        # read-only scrape of a public page, so retry unverified.
        return urllib.request.urlopen(req, timeout=60, context=ssl._create_unverified_context()).read()
from pathlib import Path

BASE = Path(__file__).parent
CACHE = BASE / "foundries.json"
SITE = "https://typefoundry.directory"
PORT = 8765


def scrape():
    html = _fetch(SITE + "/").decode("utf-8", "replace")

    foundries = []
    # Each card starts with <div class="foundry" and carries data attributes,
    # a thumb-container link, an img src, and a foundry--name anchor.
    blocks = html.split('<div class="foundry" ')[1:]
    for block in blocks:
        def attr(name):
            m = re.search(r'data-%s="([^"]*)"' % re.escape(name), block)
            return m.group(1) if m else ""

        href = re.search(r'class="thumb-container" href="([^"]+)"', block)
        img = re.search(r'src="(/images/screenshot/[^"]+)"', block)
        name = re.search(r'foundry--name">\s*<a[^>]*>([^<]+)', block)
        if not (href and name):
            continue
        img_path = img.group(1) if img else ""
        # Prefer the 800w optimized variant for crisp-but-light thumbnails.
        thumb = img_path.replace("/images/screenshot/", "/images/screenshot/optimized/").replace(".png", "-800w.png") if img_path else ""
        foundries.append({
            "name": name.group(1).strip(),
            "sort": attr("sort-name") or name.group(1).strip().lower(),
            "url": href.group(1),
            "thumb": SITE + thumb if thumb else "",
            "thumb_full": SITE + img_path if img_path else "",
            "founded": attr("founded"),
            "countries": attr("countries"),
            "languages": attr("language-support"),
            "license_type": attr("license-type"),
            "webfonts": attr("webfonts"),
            "variable_fonts": attr("variable-fonts"),
            "trial_fonts": attr("trial-fonts"),
            "student_discount": attr("student-discount"),
            "modifications_allowed": attr("modifications-allowed"),
            "adobe_fonts": attr("adobe-fonts"),
            "fontstand": attr("fontstand"),
            "future_fonts": attr("future-fonts"),
            "instagram": attr("instagram"),
        })

    if not foundries:
        raise RuntimeError("Scrape parsed 0 foundries — the site's HTML may have changed. Kept the previous cache.")
    foundries.sort(key=lambda f: f["sort"])
    data = {"pulled_at": time.strftime("%Y-%m-%d %H:%M:%S"), "count": len(foundries), "foundries": foundries}
    CACHE.write_text(json.dumps(data, indent=1))
    return data




# ---- live homepage snapshots (mShots), cached as static files in thumbs/ ----
import re as _re

THUMBS = Path(__file__).parent / "thumbs"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"}


def _slug(url):
    return _re.sub(r"[^a-z0-9.-]+", "_", url.split("://", 1)[-1].strip("/").lower())[:80]


def _mshots(url, w=600):
    return "https://s0.wp.com/mshots/v1/" + url + "?w=%d" % w


def _get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        r = urllib.request.urlopen(req, timeout=30, context=SSL_CTX)
    except (ssl.SSLError, urllib.error.URLError):
        r = urllib.request.urlopen(req, timeout=30, context=ssl._create_unverified_context())
    return r.headers.get_content_type(), r.read()


ERROR_IMAGE_MD5 = "fddb256cea6d448026d1e98a05d32dc3"  # mShots' own 404 placeholder


def fetch_snapshots(foundries, rounds=6, wait=20):
    """Download live homepage previews for foundries missing a local thumb.
    mShots renders on first request, so warm every URL then poll a few rounds."""
    THUMBS.mkdir(exist_ok=True)
    for f in foundries:
        f["thumb_local"] = ""
        path = THUMBS / (_slug(f["url"]) + ".jpg")
        if path.exists() and path.stat().st_size > 5000:
            f["thumb_local"] = "thumbs/" + path.name
    missing = [f for f in foundries if not f["thumb_local"]]
    print(f"snapshots: {len(foundries) - len(missing)} cached, {len(missing)} to fetch")
    for rnd in range(rounds):
        if not missing:
            break
        still = []
        for f in missing:
            path = THUMBS / (_slug(f["url"]) + ".jpg")
            try:
                ctype, body = _get(_mshots(f["url"]))
                import hashlib
                if ctype == "image/jpeg" and len(body) > 5000 and hashlib.md5(body).hexdigest() != ERROR_IMAGE_MD5:
                    path.write_bytes(body)
                    f["thumb_local"] = "thumbs/" + path.name
                else:
                    still.append(f)  # still rendering (loading gif)
            except Exception:
                still.append(f)
        print(f"  round {rnd + 1}: {len(missing) - len(still)} captured, {len(still)} pending")
        missing = still
        if missing and rnd < rounds - 1:
            time.sleep(wait)
    if missing:
        print(f"  {len(missing)} sites had no capturable preview (will use fallback images)")


if __name__ == "__main__":
    old = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    d = scrape()
    print(f"pulled {d['count']} foundries")
    fetch_snapshots(d["foundries"])
    if d["foundries"] == old.get("foundries"):
        # Nothing changed — restore the previous file (incl. its pulled_at)
        # so git sees no diff and no pointless deploy is triggered.
        CACHE.write_text(json.dumps(old, indent=1))
        print("no changes since last pull — skipping update")
    else:
        CACHE.write_text(json.dumps(d, indent=1))
        done = sum(1 for f in d["foundries"] if f["thumb_local"])
        print(f"data updated — local previews: {done}/{d['count']}")
