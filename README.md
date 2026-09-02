<div align="center">

# 🟠 Unique City — سرور CS2

**یک کامیونیتی سرور Counter-Strike 2 با محوریت بازیکن**

بهترین کامیونیتی CS2 برای بازیکنانی که بیشتر از یک بازی معمولی می‌خوان — اخبار زنده، تورنومنت‌ها، رنکینگ جهانی، و یه سایت که واقعاً بهش رسیدگی می‌شه.

[![GitHub Pages](https://img.shields.io/github/deployments/BigYahoo7722/Uniqe_City_server_cs2/github-pages?label=Live%20Site&logo=github)](https://bigyahoo7722.github.io/Uniqe_City_server_cs2/)
[![News Bot](https://img.shields.io/github/actions/workflow/status/BigYahoo7722/Uniqe_City_server_cs2/news-bot.yml?label=News%20Bot&logo=githubactions)](https://github.com/BigYahoo7722/Uniqe_City_server_cs2/actions)
[![Last Commit](https://img.shields.io/github/last-commit/BigYahoo7722/Uniqe_City_server_cs2?label=Last%20Update)](https://github.com/BigYahoo7722/Uniqe_City_server_cs2/commits/main)
[![License](https://img.shields.io/badge/license-MIT-orange)](#-لایسنس)

[🌐 مشاهده‌ی سایت](https://bigyahoo7722.github.io/Uniqe_City_server_cs2/) · [💬 تلگرام](https://t.me/unique3ity) · [🎮 اتصال به سرور](steam://connect/5.57.32.32:28208)

</div>

---

## ✨ امکانات

| | |
|---|---|
| 🗞️ **اخبار زنده‌ی CS2** | جمع‌آوری و ترجمه‌ی خودکار اخبار، ترانسفرها و آپدیت‌های رسمی بازی — هر ساعت به‌روز می‌شه |
| 🏆 **رنکینگ جهانی تیم‌ها** | ۱۰ تیم برتر دنیا مستقیم از HLTV |
| ⚔️ **نتایج و مسابقات** | آخرین نتایج و رویدادهای تورنومنتی از Liquipedia |
| 🎮 **وضعیت زنده‌ی سرور** | تعداد بازیکن آنلاین و نقشه‌ی فعلی، مستقیم از خود سرور بازی |
| 🛠️ **نقشه‌های ورک‌شاپ** | جدیدترین محتوای کامیونیتی از Steam Workshop |
| 👥 **عضویت و تیم مدیریت** | فرم ثبت‌نام و معرفی ادمین‌ها |
| 📱 **PWA** | قابل نصب رو موبایل مثل یه اپلیکیشن واقعی |
| 🎬 **تجربه‌ی ورود سینمایی** | انیمیشن در + بخار + خوش‌آمدگویی صوتی |

---

## 🧱 معماری

```
┌─────────────────┐      هر ساعت       ┌──────────────────┐      REST API      ┌──────────────┐
│  GitHub Actions   │ ─────────────────▶ │   news_bot.py      │ ─────────────────▶ │   Supabase     │
│  (Cron Scheduler)  │                    │  (جمع‌آوری + ترجمه) │                    │  (PostgreSQL)   │
└─────────────────┘                    └──────────────────┘                    └───────┬──────┘
                                                                                          │
                                                                                   خواندن عمومی (anon)
                                                                                          │
                                                                                          ▼
                                                                                 ┌──────────────┐
                                                                                 │  index.html    │
                                                                                 │ (GitHub Pages)  │
                                                                                 └──────────────┘
```

**منابع داده‌ی ربات:**

| منبع | نوع داده | پایداری |
|---|---|---|
| [HLTV.org](https://hltv.org) RSS | اخبار، ترانسفرها | ✅ رسمی |
| Steam Community RSS | آپدیت‌های رسمی Valve | ✅ رسمی |
| Steam Workshop RSS | نقشه‌های کامیونیتی | ⚠️ نیمه‌رسمی |
| [Liquipedia](https://liquipedia.net/counterstrike) | نتایج و مسابقات | ⚠️ best-effort |
| HLTV Rankings | رنکینگ تیم‌ها | ⚠️ best-effort |
| A2S Query Protocol | وضعیت زنده‌ی سرور | ✅ پروتکل رسمی Source Engine |

---

## 📁 ساختار پروژه

```
Uniqe_City_server_cs2/
├── index.html                    # کل سایت (HTML + CSS + JS در یک فایل)
├── manifest.json                 # تنظیمات PWA
├── sw.js                         # Service Worker
├── news_bot.py                   # ربات پایتون جمع‌آوری اخبار
├── requirements.txt              # وابستگی‌های پایتون
├── icons/                        # فاویکون و آیکون‌های PWA
├── audio/                        # صدای خوش‌آمدگویی
└── .github/
    └── workflows/
        └── news-bot.yml          # اجرای خودکار ربات (هر ساعت)
```

---

## 🚀 راه‌اندازی

پروژه از **Supabase** به‌عنوان دیتابیس و **GitHub Actions** برای اجرای زمان‌بندی‌شده‌ی ربات استفاده می‌کنه.

### ۱. دیتابیس (Supabase)

یه پروژه‌ی رایگان تو [supabase.com](https://supabase.com) بساز، و اسکیمای دیتابیس رو از SQL Editor اجرا کن (جدول‌های `cs_news`, `cs_rankings`, `cs_server_status`, `cs_analytics`, `members` رو می‌سازه).

### ۲. Secrets گیت‌هاب

تو تنظیمات ریپو (**Settings → Secrets and variables → Actions**) این دوتا رو اضافه کن:

| Secret | مقدار |
|---|---|
| `SUPABASE_URL` | آدرس پروژه‌ی Supabase |
| `SUPABASE_SERVICE_KEY` | کلید `service_role` (نه anon!) |

### ۳. کلید anon سمت فرانت‌اند

تو `index.html` مقادیر `SUPABASE_URL` و `SUPABASE_ANON_KEY` رو با اطلاعات پروژه‌ت جایگزین کن (کلید anon، نه service_role — این یکی امن برای افشای عمومیه).

### ۴. اجرای ربات

ربات خودکار **هر ساعت** با GitHub Actions اجرا می‌شه. برای اجرای دستی: تب **Actions → CS2 News Bot → Run workflow**.

---

## 🛠️ تکنولوژی‌ها

<div align="center">

![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)
![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?logo=javascript&logoColor=black)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?logo=supabase&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?logo=githubactions&logoColor=white)
![GitHub Pages](https://img.shields.io/badge/GitHub_Pages-222222?logo=githubpages&logoColor=white)

</div>

بدون فریم‌ورک، بدون build step — یه فایل HTML تک‌صفحه‌ای که مستقیم رو GitHub Pages سرو می‌شه، به‌علاوه‌ی یه ربات پایتون که پشت‌صحنه کار می‌کنه.

---

## 🔒 امنیت و حریم خصوصی

- جدول ثبت‌نام کاربران (`members`) با Row Level Security فقط اجازه‌ی **نوشتن** به بازدیدکننده‌ها می‌ده، نه خوندن.
- آنالیتیکس سایت (`cs_analytics`) هیچ کوکی، IP، یا شناسه‌ی شخصی ذخیره نمی‌کنه — فقط مسیر صفحه و ریفرر.
- کلید `service_role` (دسترسی کامل دیتابیس) فقط تو GitHub Secrets نگه داشته می‌شه، هیچ‌وقت تو کد فرانت‌اند نیست.

---

## 📜 لایسنس

MIT — آزاد برای استفاده، تغییر و توسعه.

---

<div align="center">

ساخته‌شده با ❤️ توسط **Big_Yahoo** — هاست‌شده روی [مکس گیمینگ](https://maxgaming.ir/fa)

</div>
