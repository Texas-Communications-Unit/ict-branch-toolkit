const SHELL_CACHE = "ict-toolkit-shell-v1";
const RUNTIME_CACHE = "ict-toolkit-runtime-v1";
const SHELL_URLS = [
  "/",
  "/manifest.webmanifest",
  "/brand/tx-comu-app-icon.png",
];
const CACHEABLE_PATHS = new Set(SHELL_URLS);
const CACHEABLE_PATH_PREFIXES = ["/assets/", "/brand/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      const rootResponse = await fetch("/");
      if (!rootResponse.ok) {
        throw new Error("Unable to cache the offline application shell.");
      }
      const html = await rootResponse.clone().text();
      const assetPaths = [
        ...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g),
      ].map((match) => match[1]);
      await cache.put("/", rootResponse);
      await cache.addAll([
        ...SHELL_URLS.filter((value) => value !== "/"),
        ...new Set(assetPaths),
      ]);
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== SHELL_CACHE && key !== RUNTIME_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    (!CACHEABLE_PATHS.has(url.pathname) &&
      !CACHEABLE_PATH_PREFIXES.some((prefix) =>
        url.pathname.startsWith(prefix),
      ))
  ) {
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          void caches.open(RUNTIME_CACHE).then((cache) => cache.put("/", copy));
          return response;
        })
        .catch(async () => {
          return (
            (await caches.match("/")) ??
            new Response("ICT Toolkit is unavailable offline on this device.", {
              status: 503,
              headers: { "Content-Type": "text/plain; charset=utf-8" },
            })
          );
        }),
    );
    return;
  }
  event.respondWith(
    caches.match(url.pathname, { ignoreSearch: true, ignoreVary: true }).then(
      (cached) =>
        cached ??
        fetch(request).then((response) => {
          if (!response.ok) return response;
          const copy = response.clone();
          void caches
            .open(RUNTIME_CACHE)
            .then((cache) => cache.put(request, copy));
          return response;
        }),
    ),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type === "ACTIVATE_UPDATE") {
    void self.skipWaiting();
    return;
  }
  if (event.data?.type === "PURGE_RUNTIME_CACHES") {
    event.waitUntil(
      caches
        .delete(RUNTIME_CACHE)
        .then(() => event.ports[0]?.postMessage({ ok: true }))
        .catch(() => event.ports[0]?.postMessage({ ok: false })),
    );
  }
});
