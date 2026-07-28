export const SERVICE_WORKER_UPDATE_EVENT = "ict-toolkit-service-worker-update";

export async function registerOfflineServiceWorker(): Promise<
  ServiceWorkerRegistration | undefined
> {
  if (!("serviceWorker" in navigator)) return undefined;
  const registration = await navigator.serviceWorker.register(
    "/offline-service-worker.js",
    { scope: "/" },
  );
  if (registration.waiting) {
    window.dispatchEvent(new Event(SERVICE_WORKER_UPDATE_EVENT));
  }
  registration.addEventListener("updatefound", () => {
    const worker = registration.installing;
    worker?.addEventListener("statechange", () => {
      if (worker.state === "installed" && navigator.serviceWorker.controller) {
        window.dispatchEvent(new Event(SERVICE_WORKER_UPDATE_EVENT));
      }
    });
  });
  return registration;
}

export async function checkForOfflineUpdate(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/");
  await registration?.update();
}

export async function activateOfflineUpdate(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/");
  registration?.waiting?.postMessage({ type: "ACTIVATE_UPDATE" });
}

export async function clearOfflineRuntimeCaches(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const registration = await navigator.serviceWorker.getRegistration("/");
  const worker =
    navigator.serviceWorker.controller ??
    registration?.active ??
    registration?.waiting;
  if (!worker) return;
  await new Promise<void>((resolve, reject) => {
    const channel = new MessageChannel();
    const timeout = window.setTimeout(
      () => reject(new Error("Cache clearing did not complete.")),
      5_000,
    );
    channel.port1.onmessage = (event) => {
      window.clearTimeout(timeout);
      if (event.data?.ok) resolve();
      else reject(new Error("Cache clearing did not complete."));
    };
    worker.postMessage({ type: "PURGE_RUNTIME_CACHES" }, [channel.port2]);
  });
}
