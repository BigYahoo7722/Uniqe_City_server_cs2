#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unique City CS2 — News / Tournament / Update aggregator bot
"""

import os
import re
import sys
import hashlib
import logging
from datetime import datetime, timezone

import requests
import feedparser
from dateutil import parser as dateparser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("news_bot")

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TABLE = "cs_news"

MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "15"))

SOURCES = [
    {
        "name": "HLTV",
        "url": "https://www.hltv.org/rss/news",
        "default_type": "news",
    },
    {
        "name": "Valve / Steam",
        "url": "https://steamcommunity.com/games/csgo/rss/",
        "default_type": "update",
    },
]

TOURNAMENT_KEYWORDS = [
    "major", "iem", "esl pro league", "blast", "pgl", "cologne", "katowice",
    "playoffs", "grand final", "champion", "qualifier", "tournament",
    "پلی‌آف", "قهرمانی", "تورنومنت", "فینال",
]


def classify(title: str, summary: str, default_type: str) -> str:
    if default_type == "update":
        return "update"
    text = f"{title} {summary}".lower()
    for kw in TOURNAMENT_KEYWORDS:
        if kw in text:
            return "tournament"
    return default_type


def strip_html(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:280] + "…") if len(text) > 280 else text


def extract_image(entry) -> str:
    for field in ("media_content", "media_thumbnail"):
        media = entry.get(field)
        if media and isinstance(media, list) and media[0].get("url"):
            return media[0]["url"]
    if entry.get("links"):
        for link in entry["links"]:
            if link.get("type", "").startswith("image"):
                return link.get("href", "")
    html_blob = entry.get("summary", "") or entry.get("description", "")
    m = re.search(r'<img[^>]+src="([^"]+)"', html_blob)
    if m:
        return m.group(1)
    return ""


def make_external_id(link: str) -> str:
    return hashlib.sha256(link.encode("utf-8")).hexdigest()[:32]


def parse_published(entry) -> str:
    for field in ("published", "updated", "pubDate"):
        val = entry.get(field)
        if val:
            try:
                dt = dateparser.parse(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except (ValueError, TypeError):
                continue
    return datetime.now(timezone.utc).isoformat()


def fetch_source(source: dict) -> list:
    items = []
    try:
        log.info("در حال دریافت از %s ...", source["name"])
        feed = feedparser.parse(source["url"])
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"RSS نامعتبر یا در دسترس نبود: {feed.bozo_exception}")

        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            summary_raw = entry.get("summary", "") or entry.get("description", "")
            summary = strip_html(summary_raw)
            item_type = classify(title, summary, source["default_type"])

            items.append({
                "type": item_type,
                "title": title[:300],
                "summary": summary,
                "image_url": extract_image(entry) or None,
                "source_name": source["name"],
                "source_url": link,
                "external_id": make_external_id(link),
                "published_at": parse_published(entry),
            })
        log.info("  → %d آیتم از %s پردازش شد", len(items), source["name"])
    except Exception as exc:  # noqa: BLE001
        log.error("شکست در دریافت منبع %s: %s", source["name"], exc)
    return items


def push_to_supabase(records: list) -> None:
    if not records:
        log.info("رکوردی برای ارسال وجود نداره.")
        return
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        log.error("SUPABASE_URL یا SUPABASE_SERVICE_KEY تنظیم نشده؛ از GitHub Secrets چک کن.")
        sys.exit(1)

    endpoint = f"{SUPABASE_URL}/rest/v1/{TABLE}?on_conflict=source_name,external_id"
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    batch_size = 50
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        resp = requests.post(endpoint, headers=headers, json=batch, timeout=30)
        if resp.status_code >= 300:
            log.error("خطا در ارسال به Supabase (%d): %s", resp.status_code, resp.text[:500])
        else:
            log.info("✔ %d رکورد با موفقیت ثبت/به‌روزرسانی شد", len(batch))


def main():
    log.info("شروع اجرای ربات اخبار CS2 ...")
    all_records = []
    for source in SOURCES:
        all_records.extend(fetch_source(source))

    log.info("مجموع %d رکورد از %d منبع جمع‌آوری شد.", len(all_records), len(SOURCES))
    push_to_supabase(all_records)
    log.info("اجرای ربات با موفقیت تمام شد.")


if __name__ == "__main__":
    main()
