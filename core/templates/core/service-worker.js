{% load static %}
const CACHE_PREFIX = 'veludo-grao-pwa-';
const CACHE_NAME = `${CACHE_PREFIX}v1`;
const OFFLINE_URL = '{% url "core:offline" %}';
const ASSETS = [
  OFFLINE_URL,
  '{% static "icons/icon.svg" %}',
  '{% static "icons/icon-192.png" %}',
  '{% static "icons/icon-512.png" %}',
  '{% static "icons/icon-maskable-192.png" %}',
  '{% static "icons/icon-maskable-512.png" %}',
  '{% static "icons/apple-touch-icon.png" %}',
  '{% static "icons/favicon.ico" %}',
];

self.addEventListener('install', event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(ASSETS);
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    // Never store customer pages, tracking, checkout, or administrative responses.
    event.respondWith(fetch(request).catch(async () => {
      const cache = await caches.open(CACHE_NAME);
      const fallback = await cache.match(OFFLINE_URL);
      if (!fallback) return Response.error();
      return new Response(await fallback.text(), {
        status: 503,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' },
      });
    }));
  } else if (ASSETS.includes(url.pathname) && !url.search) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      return (await cache.match(request)) || fetch(request);
    })());
  }
});
