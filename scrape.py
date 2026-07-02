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


if __name__ == "__main__":
    d = scrape()
    print(f"pulled {d['count']} foundries")
