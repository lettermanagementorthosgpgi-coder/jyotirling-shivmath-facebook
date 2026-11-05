#!/usr/bin/env python3
"""Build static HTML pages for videos owned by a Facebook Page.

Read-only: this script never writes to Facebook. Credentials are read only
from environment variables and are never printed or persisted.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "public" / "facebook"
INDEX_FILE = ROOT / "data" / "facebook_videos.json"
SITEMAP_FILE = ROOT / "public" / "sitemap-facebook.xml"
PAGE_FIELDS = "id,title,description,created_time,permalink_url,picture"
TIMEOUT = 30


def env_required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:70] or "facebook-video"


def fetch_videos(page_id: str, token: str, api_version: str) -> list[dict]:
    url = f"https://graph.facebook.com/{api_version}/{quote(page_id, safe='')}/videos"
    params = {"fields": PAGE_FIELDS, "limit": 50, "access_token": token}
    session = requests.Session()
    videos: list[dict] = []

    while url:
        response = session.get(url, params=params, timeout=TIMEOUT)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"Meta API returned non-JSON response (HTTP {response.status_code})") from exc

        if not response.ok or "error" in payload:
            error = payload.get("error", {})
            # Never include request URLs: they contain the access token.
            message = error.get("message", f"HTTP {response.status_code}")
            code = error.get("code", "unknown")
            raise RuntimeError(f"Meta Graph API error {code}: {message}")

        videos.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
        params = None  # next URL already contains paging parameters
        if url:
            time.sleep(0.2)

    return videos


def load_index() -> dict:
    if not INDEX_FILE.exists():
        return {}
    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def make_html(video: dict, canonical_url: str) -> str:
    title = html.escape(video.get("title") or "Facebook Video")
    description = html.escape(video.get("description") or "")
    video_url = html.escape(video.get("permalink_url") or "", quote=True)
    image_url = html.escape(video.get("picture") or "", quote=True)
    created = html.escape(video.get("created_time") or "")
    image = f'<img src="{image_url}" alt="{title}" class="cover">' if image_url else ""
    description_block = f"<p>{description}</p>" if description else ""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} | Jyotirling Shivmath</title>
<meta name="description" content="{description[:250]}">
<link rel="canonical" href="{html.escape(canonical_url, quote=True)}">
<meta property="og:type" content="video.other">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description[:250]}">
<meta property="og:image" content="{image_url}">
<style>
body{{font-family:Arial,sans-serif;max-width:900px;margin:32px auto;padding:0 16px;line-height:1.65;color:#222}}
header,footer{{text-align:center}} .cover{{display:block;max-width:100%;height:auto;margin:20px auto;border-radius:12px}}
.video-link{{display:inline-block;padding:12px 18px;background:#6b1d1d;color:#fff;text-decoration:none;border-radius:8px}}
small{{color:#666}} h1{{line-height:1.25}}
</style>
</head>
<body>
<header><strong>JYOTIRLING SHIVMATH</strong><p>Barouli, Lucknow</p></header>
<main>
<h1>{title}</h1>
<small>{created}</small>
{image}
{description_block}
<p><a class="video-link" href="{video_url}" rel="noopener" target="_blank">Watch video on Facebook</a></p>
</main>
<footer><hr><p>Jyotirling Shivmath, Lucknow</p></footer>
</body>
</html>
"""


def main() -> int:
    page_id = env_required("FB_PAGE_ID")
    token = env_required("FB_PAGE_ACCESS_TOKEN")
    api_version = os.getenv("FB_GRAPH_API_VERSION", "v26.0").strip()
    site_base = os.getenv("SITE_BASE_URL", "https://jyotirlingshivmath.in").strip().rstrip("/")
    if not re.fullmatch(r"v\d+\.\d+", api_version):
        raise RuntimeError("FB_GRAPH_API_VERSION must look like v26.0")
    if not site_base.startswith("https://"):
        raise RuntimeError("SITE_BASE_URL must be an https:// URL")

    videos = fetch_videos(page_id, token, api_version)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    known = load_index()
    sitemap_urls: list[tuple[str, str]] = []

    for video in videos:
        video_id = str(video.get("id", "")).strip()
        if not video_id:
            continue
        title = video.get("title") or "Facebook Video"
        slug = safe_slug(title)
        filename = f"{slug}-{re.sub(r'[^0-9]', '', video_id)[-18:] or 'video'}.html"
        relative = f"facebook/{filename}"
        canonical = f"{site_base}/{relative}"
        target = OUTPUT_DIR / filename
        target.write_text(make_html(video, canonical), encoding="utf-8")
        known[video_id] = {
            "file": relative,
            "title": title,
            "created_time": video.get("created_time", ""),
            "permalink_url": video.get("permalink_url", ""),
        }
        sitemap_urls.append((canonical, video.get("created_time", "")))

    # Retain previously generated pages in sitemap even if Meta omits older
    # videos from the current API page window.
    for item in known.values():
        rel = item.get("file")
        if rel:
            canonical = f"{site_base}/{rel.lstrip('/')}"
            if all(existing[0] != canonical for existing in sitemap_urls):
                sitemap_urls.append((canonical, item.get("created_time", "")))

    INDEX_FILE.write_text(json.dumps(known, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    now = datetime.now(timezone.utc).date().isoformat()
    entries = []
    for loc, lastmod in sorted(sitemap_urls):
        lastmod = (lastmod or "")[:10] or now
        entries.append(f"  <url><loc>{html.escape(loc)}</loc><lastmod>{html.escape(lastmod)}</lastmod></url>")
    SITEMAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    SITEMAP_FILE.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(entries)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    print(f"Videos received from Page API: {len(videos)}")
    print(f"Known video pages in index: {len(known)}")
    print(f"Generated sitemap entries: {len(sitemap_urls)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
