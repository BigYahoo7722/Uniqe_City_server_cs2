#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unique City CS2 — News / Tournament / Ranking / Workshop aggregator bot
=========================================================================
هر بار که اجرا میشه:
  1) از منابع معتبر تعریف‌شده در SOURCES خبر جمع می‌کنه (RSS).
  2) از Liquipedia آخرین نتایج و مسابقات پیش‌رو رو می‌گیره.
  3) از HLTV رنکینگ فعلی تیم‌ها رو می‌گیره.
  4) از Steam Workshop نقشه‌های جدید کامیونیتی رو می‌گیره.
  5) هر خبر رو نرمال‌سازی و دسته‌بندی می‌کنه (news / tournament / update / workshop).
  6) با external_id یکتا (هش لینک) جلوی خبر تکراری رو می‌گیره.
  7) با upsert داخل جدول cs_news و بازنویسی کامل جدول cs_rankings توی Supabase ثبت می‌کنه.

این اسکریپت قراره هر ساعت یک‌بار توسط GitHub Actions اجرا بشه
(فایل .github/workflows/news-bot.yml رو ببین).

⚠️ نکته‌ی مهم درباره‌ی "زنده" بودن:
این ربات هر ساعت اجرا میشه، پس چیزی که از Liquipedia می‌گیریم "آخرین نتایج و
مسابقات پیش‌رو"ست نه یه اسکوربورد لحظه‌به‌لحظه. برای اسکور واقعاً زنده به یه
معماری کاملاً متفاوت (پولینگ مداوم یا وب‌سوکت) نیاز داری.

⚠️ نکته‌ی مهم درباره‌ی پایداری منابع:
منابع RSS (HLTV News, Valve/Steam) قراردادی و پایدارن. اما Liquipedia و رنکینگ
HLTV با اسکرپ HTML کار می‌کنن — اگه اون سایت‌ها ساختار صفحه‌شون رو عوض کنن،
ممکنه اون تابع خاص دیگه چیزی برنگردونه. به همین خاطر هرکدوم مستقل try/except
دارن؛ خرابی یکی باعث توقف بقیه‌ی ربات نمیشه. اگه بعد از اجرا دیدی رنکینگ یا
تورنومنت‌ها خالی موندن، لاگ اجرا رو تو تب Actions چک کن — احتمالاً selectorها
نیاز به آپدیت دارن.

⚠️ نکته‌ی مهم درباره‌ی ترجمه:
عنوان و خلاصه‌ی خبرها (که اصلشون انگلیسی‌ان) قبل از ذخیره تو Supabase با یه
سرویس ترجمه‌ی رایگان به فارسی برگردونده میشن. اگه ترجمه برای یه آیتم خاص شکست
بخوره (قطعی سرویس، محدودیت نرخ و غیره)، متن اصلی انگلیسی به‌جاش ذخیره میشه —
یعنی خبر گم نمیشه، فقط ممکنه یه مورد نادر انگلیسی بمونه تا اجرای بعدی.

منابع فعلی:
  - HLTV.org RSS      → اخبار، ترانسفرها، نتایج (رسمی/پایدار)
  - Steam Community    → آپدیت‌های رسمی CS2 از طرف Valve (رسمی/پایدار)
  - Liquipedia          → نتایج اخیر و مسابقات پیش‌رو (best-effort/HTML)
  - HLTV Rankings       → رنکینگ فعلی ۱۰ تیم برتر جهان (best-effort/HTML)
  - Steam Workshop      → جدیدترین نقشه‌های کامیونیتی CS2 (best-effort/RSS)
"""

import os
import re
import sys
import time
import hashlib
import logging
from datetime import datetime, timezone

import requests
import feedparser
from dateutil import parser as dateparser
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

# Liquipedia از هرکسی که به API/سایتشون درخواست می‌زنه می‌خواد یه User-Agent
# مشخص و قابل‌شناسایی معرفی کنه (طبق قوانین استفاده‌شون).
HTTP_HEADERS = {
    "User-Agent": "UniqueCityCS2NewsBot/1.0 (+https://github.com/BigYahoo7722/Uniqe_City_server_cs2)"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("news_bot")

# ──────────────────────────────────────────────────────────────
# تنظیمات Supabase — از GitHub Secrets خونده میشن (هیچ‌وقت مستقیم اینجا ننویس)
# ──────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
TABLE = "cs_news"

# چند تا خبر از هر منبع در هر اجرا بررسی بشه (برای جلوگیری از ارسال حجم زیاد در اولین اجرا)
MAX_ITEMS_PER_SOURCE = int(os.environ.get("MAX_ITEMS_PER_SOURCE", "15"))

# ──────────────────────────────────────────────────────────────
# منابع خبری — هرکدوم یک RSS معتبر و رسمی/نیمه‌رسمی هستن
# ──────────────────────────────────────────────────────────────
SOURCES = [
    {
        "name": "HLTV",
        "url": "https://www.hltv.org/rss/news",
        # پیش‌فرض این منبع "news" هست، ولی اگه کلیدواژه‌ی تورنومنت داشت type عوض میشه
        "default_type": "news",
    },
    {
        "name": "Valve / Steam",
        "url": "https://steamcommunity.com/games/csgo/rss/",
        # این منبع همیشه از طرف خود Valve هست => آپدیت رسمی بازی
        "default_type": "update",
    },
]

# آدرس RSS مرور ورک‌شاپ Steam برای CS2 (appid=730)، جدیدترین آیتم‌ها.
# نکته: این یه قابلیت نیمه‌رسمی Steam‌ه (نه یک RSS تضمین‌شده مثل بقیه)،
# پس best-effort با try/except جدا مدیریت میشه.
WORKSHOP_RSS_URL = "https://steamcommunity.com/workshop/browse/rss/?appid=730&browsesort=mostrecent&section=readytouseitems"

# صفحه‌ی Liquipedia که نتایج اخیر و مسابقات پیش‌رو رو نشون میده
LIQUIPEDIA_MATCHES_URL = "https://liquipedia.net/counterstrike/Liquipedia:Matches"

# صفحه‌ی رنکینگ جهانی تیم‌ها در HLTV
HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams"

# کلیدواژه‌هایی که نشون میدن خبر درباره‌ی یک تورنومنت/رویداد رقابتیه
TOURNAMENT_KEYWORDS = [
    "major", "iem", "esl pro league", "blast", "pgl", "cologne", "katowice",
    "playoffs", "grand final", "champion", "qualifier", "tournament",
    "پلی‌آف", "قهرمانی", "تورنومنت", "فینال",
]


def classify(title: str, summary: str, default_type: str) -> str:
    """بر اساس کلیدواژه‌ها نوع خبر رو تشخیص میده؛ اگه منبع رسمی Valve بود همیشه 'update' می‌مونه."""
    if default_type == "update":
        return "update"
    text = f"{title} {summary}".lower()
    for kw in TOURNAMENT_KEYWORDS:
        if kw in text:
            return "tournament"
    return default_type


def strip_html(raw: str) -> str:
    """تگ‌های HTML رو از خلاصه‌ی RSS حذف می‌کنه و متن رو کوتاه می‌کنه."""
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\s+", " ", text).strip()
    return (text[:280] + "…") if len(text) > 280 else text


def translate_to_fa(text: str) -> str:
    """متن انگلیسی رو با یه سرویس ترجمه‌ی رایگان (بدون نیاز به کلید API) به
    فارسی برمی‌گردونه. اگه سرویس در دسترس نبود یا خطا داد، خود متن اصلی
    (انگلیسی) رو برمی‌گردونه — یعنی خبر همیشه ذخیره میشه، فقط شاید یه‌بار
    ترجمه نشده بمونه تا اجرای بعدی که دوباره امتحان بشه.
    یه مکث کوچیک بین هر درخواست می‌ذاریم تا سرویس رایگان محدودمون نکنه."""
    if not text or not text.strip():
        return text
    try:
        translated = GoogleTranslator(source="en", target="fa").translate(text)
        time.sleep(0.35)  # جلوگیری از rate-limit سرویس رایگان
        return translated if translated else text
    except Exception as exc:  # noqa: BLE001
        log.warning("ترجمه ناموفق بود، متن اصلی نگه داشته شد: %s", exc)
        return text


def extract_image(entry) -> str:
    """تلاش می‌کنه یک عکس مرتبط از فیلدهای مختلف RSS استخراج کنه."""
    # media_content / media_thumbnail (فرمت رایج RSS رسانه‌ای)
    for field in ("media_content", "media_thumbnail"):
        media = entry.get(field)
        if media and isinstance(media, list) and media[0].get("url"):
            return media[0]["url"]
    # enclosure
    if entry.get("links"):
        for link in entry["links"]:
            if link.get("type", "").startswith("image"):
                return link.get("href", "")
    # عکس داخل خود summary/description (اولین تگ <img>)
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
    """یک منبع RSS رو می‌خونه و لیستی از رکوردهای نرمال‌شده برمی‌گردونه.
    هر منبع مستقل try/except داره تا خرابی یک منبع بقیه رو متوقف نکنه."""
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
            # دسته‌بندی باید روی متن اصلی انگلیسی انجام بشه، چون کلیدواژه‌ها
            # (major, iem, playoffs و...) انگلیسی‌ان؛ بعد از تشخیص نوع، ترجمه می‌کنیم.
            item_type = classify(title, summary, source["default_type"])
            title_fa = translate_to_fa(title[:300])
            summary_fa = translate_to_fa(summary)

            items.append({
                "type": item_type,
                "title": title_fa,
                "summary": summary_fa,
                "image_url": extract_image(entry) or None,
                "source_name": source["name"],
                "source_url": link,
                "external_id": make_external_id(link),
                "published_at": parse_published(entry),
            })
        log.info("  → %d آیتم از %s پردازش شد", len(items), source["name"])
    except Exception as exc:  # noqa: BLE001  — هر خطایی که باشه لاگ میشه، اجرای کل ربات متوقف نمیشه
        log.error("شکست در دریافت منبع %s: %s", source["name"], exc)
    return items


def fetch_workshop() -> list:
    """جدیدترین نقشه‌های ورک‌شاپ CS2 رو از RSS مرور Steam می‌گیره.
    best-effort: اگه Steam این RSS رو عوض/غیرفعال کنه، فقط یه لیست خالی برمی‌گرده
    و بقیه‌ی ربات بدون مشکل ادامه پیدا می‌کنه."""
    items = []
    try:
        log.info("در حال دریافت آیتم‌های ورک‌شاپ Steam ...")
        feed = feedparser.parse(WORKSHOP_RSS_URL, request_headers=HTTP_HEADERS)
        if feed.bozo and not feed.entries:
            raise RuntimeError(f"RSS ورک‌شاپ نامعتبر یا در دسترس نبود: {feed.bozo_exception}")

        for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            summary = strip_html(entry.get("summary", "") or entry.get("description", ""))
            # اسم نقشه‌های ورک‌شاپ معمولاً اسم خاصه (مثل "de_dust2_remake")؛
            # فقط خلاصه رو ترجمه می‌کنیم، عنوان (اسم نقشه) دست‌نخورده می‌مونه
            # چون ترجمه‌ی اسم خاص معمولاً یا بی‌معنی میشه یا گمراه‌کننده.
            summary_fa = translate_to_fa(summary)
            items.append({
                "type": "workshop",
                "title": title[:300],
                "summary": summary_fa,
                "image_url": extract_image(entry) or None,
                "source_name": "Steam Workshop",
                "source_url": link,
                "external_id": make_external_id(link),
                "published_at": parse_published(entry),
            })
        log.info("  → %d آیتم ورک‌شاپ پردازش شد", len(items))
    except Exception as exc:  # noqa: BLE001
        log.error("شکست در دریافت ورک‌شاپ (best-effort، بی‌خطر): %s", exc)
    return items


def fetch_liquipedia_matches() -> list:
    """آخرین نتایج و مسابقات پیش‌رو رو از صفحه‌ی Matches در Liquipedia می‌گیره.
    best-effort/HTML: اگه Liquipedia قالب صفحه‌شون رو عوض کنن، این تابع ممکنه
    چیزی پیدا نکنه؛ در این صورت فقط یه لیست خالی برمی‌گردونه، خطایی که کل
    ربات رو متوقف کنه رخ نمیده."""
    items = []
    try:
        log.info("در حال دریافت مسابقات از Liquipedia ...")
        resp = requests.get(
            "https://liquipedia.net/counterstrike/api.php",
            params={
                "action": "parse",
                "page": "Liquipedia:Matches",
                "format": "json",
                "prop": "text",
            },
            headers=HTTP_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        html = resp.json().get("parse", {}).get("text", {}).get("*", "")
        if not html:
            raise RuntimeError("پاسخ Liquipedia خالی بود")

        soup = BeautifulSoup(html, "html.parser")
        # ساختار معمول جدول‌های مسابقه‌ی Liquipedia: هر ردیف مسابقه معمولاً
        # یک بلوک با کلاس‌هایی شامل نام دو تیم و اسکور/زمانه.
        match_blocks = soup.select(".match, .brkts-matchlist-match, .infobox_matches_content")
        for block in match_blocks[:MAX_ITEMS_PER_SOURCE]:
            teams = [t.get_text(strip=True) for t in block.select(".team-template-text")]
            if len(teams) < 2:
                continue
            team1, team2 = teams[0], teams[1]

            score_el = block.select_one(".versus, .match-countdown, .bracket-score")
            score_text = score_el.get_text(" ", strip=True) if score_el else "TBD"

            tournament_el = block.find_previous(class_=re.compile("tournament-text|matches-header"))
            tournament_name = tournament_el.get_text(strip=True) if tournament_el else "CS2"

            title = f"{team1} vs {team2} — {tournament_name}"
            # برای external_id چون این صفحه لینک اختصاصی به ازای هر مسابقه نداره،
            # از ترکیب نام تیم‌ها + تورنومنت هش می‌گیریم.
            uniq_key = f"{team1}|{team2}|{tournament_name}"

            items.append({
                "type": "tournament",
                "title": title[:300],
                "summary": f"نتیجه/وضعیت: {score_text} — {tournament_name}",
                "image_url": None,
                "source_name": "Liquipedia",
                "source_url": LIQUIPEDIA_MATCHES_URL,
                "external_id": make_external_id(uniq_key),
                "published_at": datetime.now(timezone.utc).isoformat(),
            })
        log.info("  → %d مسابقه از Liquipedia پردازش شد", len(items))
        if not items:
            log.warning("Liquipedia هیچ مسابقه‌ای برنگردوند — ممکنه selectorها نیاز به آپدیت داشته باشن.")
    except Exception as exc:  # noqa: BLE001
        log.error("شکست در دریافت Liquipedia (best-effort، بی‌خطر): %s", exc)
    return items


def fetch_hltv_rankings() -> list:
    """رنکینگ ۱۰ تیم برتر جهان رو از صفحه‌ی رسمی رنکینگ HLTV می‌گیره.
    best-effort/HTML — همون توضیح بالا صادقه: اگه HLTV صفحه رو عوض کنه،
    این فقط یه لیست خالی برمی‌گردونه."""
    rankings = []
    try:
        log.info("در حال دریافت رنکینگ تیم‌ها از HLTV ...")
        resp = requests.get(HLTV_RANKING_URL, headers=HTTP_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        team_rows = soup.select(".ranked-team")
        for i, row in enumerate(team_rows[:10], start=1):
            name_el = row.select_one(".name")
            points_el = row.select_one(".points")
            if not name_el:
                continue
            team_name = name_el.get_text(strip=True)
            points_text = points_el.get_text(strip=True) if points_el else ""
            points_match = re.search(r"\d+", points_text.replace(",", ""))
            points = int(points_match.group()) if points_match else None

            rankings.append({
                "rank": i,
                "team_name": team_name,
                "points": points,
                "source_name": "HLTV",
            })
        log.info("  → %d تیم از رنکینگ HLTV پردازش شد", len(rankings))
        if not rankings:
            log.warning("HLTV رنکینگی برنگردوند — ممکنه selectorها نیاز به آپدیت داشته باشن.")
    except Exception as exc:  # noqa: BLE001
        log.error("شکست در دریافت رنکینگ HLTV (best-effort، بی‌خطر): %s", exc)
    return rankings


def push_to_supabase(records: list) -> None:
    """با upsert (on_conflict) رکوردها رو داخل Supabase ثبت می‌کنه.
    اگه رکورد با همون (source_name, external_id) قبلاً وجود داشته باشه، به‌روزرسانی میشه نه تکرار."""
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

    # ارسال دسته‌ای (batch) به‌جای تک‌تک، برای کاهش تعداد درخواست‌ها
    batch_size = 50
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        resp = requests.post(endpoint, headers=headers, json=batch, timeout=30)
        if resp.status_code >= 300:
            log.error("خطا در ارسال به Supabase (%d): %s", resp.status_code, resp.text[:500])
        else:
            log.info("✔ %d رکورد با موفقیت ثبت/به‌روزرسانی شد", len(batch))


def push_rankings_to_supabase(rankings: list) -> None:
    """جدول cs_rankings یه لیدربورده، نه یه فید اخبار — پس به‌جای upsert،
    رکوردهای منبع فعلی (source_name='HLTV') رو پاک می‌کنیم و رکوردهای تازه
    رو جایگزینش می‌کنیم. این یعنی رنکینگ همیشه دقیقاً همون چیزیه که آخرین
    اجرای ربات دیده، بدون رکوردهای قدیمی باقی‌مونده."""
    if not rankings:
        log.info("رنکینگی برای ارسال وجود نداره.")
        return
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        log.error("SUPABASE_URL یا SUPABASE_SERVICE_KEY تنظیم نشده؛ از GitHub Secrets چک کن.")
        return

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    delete_endpoint = f"{SUPABASE_URL}/rest/v1/cs_rankings?source_name=eq.HLTV"
    del_resp = requests.delete(delete_endpoint, headers=headers, timeout=30)
    if del_resp.status_code >= 300:
        log.error("خطا در پاک‌سازی رنکینگ قدیمی (%d): %s", del_resp.status_code, del_resp.text[:300])
        return

    insert_endpoint = f"{SUPABASE_URL}/rest/v1/cs_rankings"
    insert_headers = dict(headers, Prefer="return=minimal")
    resp = requests.post(insert_endpoint, headers=insert_headers, json=rankings, timeout=30)
    if resp.status_code >= 300:
        log.error("خطا در ثبت رنکینگ جدید (%d): %s", resp.status_code, resp.text[:500])
    else:
        log.info("✔ رنکینگ %d تیم به‌روزرسانی شد", len(rankings))


def main():
    log.info("شروع اجرای ربات اخبار CS2 ...")

    all_records = []
    for source in SOURCES:
        all_records.extend(fetch_source(source))
    all_records.extend(fetch_workshop())
    all_records.extend(fetch_liquipedia_matches())

    log.info("مجموع %d رکورد خبر/تورنومنت/ورک‌شاپ جمع‌آوری شد.", len(all_records))
    push_to_supabase(all_records)

    rankings = fetch_hltv_rankings()
    push_rankings_to_supabase(rankings)

    log.info("اجرای ربات با موفقیت تمام شد.")


if __name__ == "__main__":
    main()
