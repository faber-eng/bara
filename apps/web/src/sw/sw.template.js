const CACHE = "bara-shell-__VERSION__";
const SHELL = __SHELL__;
const SHELL_PAGE = "/index.html";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(names.filter((name) => name !== CACHE).map((name) => caches.delete(name))),
      )
      .then(() => self.clients.claim()),
  );
});

function isShellAsset(url) {
  return url.origin === self.location.origin && SHELL.includes(url.pathname);
}

async function pageFromNetworkOrCache(request) {
  try {
    return await fetch(request);
  } catch {
    const cache = await caches.open(CACHE);
    return (await cache.match(SHELL_PAGE)) ?? Response.error();
  }
}

async function assetFromCacheOrNetwork(request) {
  const cache = await caches.open(CACHE);
  return (await cache.match(request)) ?? fetch(request);
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) return;
  if (request.mode === "navigate") {
    event.respondWith(pageFromNetworkOrCache(request));
    return;
  }
  if (isShellAsset(url)) event.respondWith(assetFromCacheOrNetwork(request));
});
