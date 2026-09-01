// ── Service Worker یونیک سیتی ──
// هدف اصلی اینجا "قابل‌نصب بودن" (Add to Home Screen) هست، نه یه استراتژی
// آفلاین سنگین. فقط پوسته‌ی سایت (index.html + آیکون‌ها) رو کش می‌کنیم تا
// اگه کاربر آفلاین شد یا اینترنتش لحظه‌ای قطع شد، صفحه‌ی سفید نبینه.
// اخبار/رنکینگ/وضعیت سرور چون از Supabase میان و باید همیشه تازه باشن،
// اصلاً کش نمی‌شن — همیشه مستقیم از شبکه درخواست داده می‌شن.

const CACHE_NAME = 'unique-city-shell-v1';
const SHELL_FILES = [
  './',
  './index.html',
  './manifest.json',
  './icons/favicon-32.png',
  './icons/favicon-64.png',
  './icons/icon-192.png',
];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(SHELL_FILES);
    }).catch(function () {
      // اگه یکی از فایل‌ها به هر دلیلی پیدا نشد، نصب رو خراب نکن
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; })
            .map(function (k) { return caches.delete(k); })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', function (event) {
  var url = event.request.url;

  // دیتای زنده (Supabase) هیچ‌وقت کش نمیشه — همیشه شبکه
  if (url.indexOf('supabase.co') !== -1) return;

  // فقط برای درخواست‌های GET همین origin از cache-first با fallback به شبکه استفاده می‌کنیم
  if (event.request.method !== 'GET') return;

  event.respondWith(
    caches.match(event.request).then(function (cached) {
      return cached || fetch(event.request).catch(function () {
        return caches.match('./index.html');
      });
    })
  );
});
