/// <reference lib="webworker" />
/**
 * Service worker DiffDuel (injectManifest, workbox).
 *
 * - Прекэш app shell (vite/workbox подставляет манифест в self.__WB_MANIFEST).
 * - Офлайн-fallback навигаций → /offline.html (страница из дизайна).
 * - Заготовка push «тебя вызвали» (без бэкенда пушей — обработчик готов к нему).
 */
import { precacheAndRoute } from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { NetworkOnly } from 'workbox-strategies';

declare const self: ServiceWorkerGlobalScope;

const OFFLINE_URL = '/offline.html';

// Прекэш статики (app shell) — список генерит сборка.
precacheAndRoute(self.__WB_MANIFEST);

// Навигации: пробуем сеть, при офлайне отдаём сохранённую offline.html.
const navigationHandler = new NetworkOnly();
registerRoute(
  new NavigationRoute(async (params) => {
    try {
      return await navigationHandler.handle(params);
    } catch {
      const cached = await caches.match(OFFLINE_URL, { ignoreSearch: true });
      return cached ?? Response.error();
    }
  }),
);

self.addEventListener('install', () => {
  void self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

/**
 * Push «тебя вызвали в дуэли/турнире».
 * Бэкенд пушей в MVP нет — обработчик готов принять payload вида
 * `{ title, body, url }` и показать уведомление.
 */
self.addEventListener('push', (event: PushEvent) => {
  let data: { title?: string; body?: string; url?: string } = {};
  try {
    data = event.data ? (event.data.json() as typeof data) : {};
  } catch {
    data = { body: event.data?.text() };
  }
  const title = data.title ?? 'DiffDuel — тебя вызвали';
  const body = data.body ?? 'Соперник ждёт. Открой приложение, чтобы принять вызов.';
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: data.url ?? '/app' },
    }),
  );
});

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();
  const url = (event.notification.data as { url?: string })?.url ?? '/app';
  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) return client.focus();
      }
      return self.clients.openWindow(url);
    }),
  );
});

export {};
