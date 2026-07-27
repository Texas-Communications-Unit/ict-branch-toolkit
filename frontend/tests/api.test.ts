import {
  AUTHENTICATION_EXPIRED_EVENT,
  hasActiveSession,
  login,
  logout,
} from "../src/api";

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

test("clears a locally expired token and notifies the interface", () => {
  sessionStorage.setItem("ict-toolkit-token", "expired-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2000-01-01T00:00:00Z",
  );
  const listener = vi.fn();
  window.addEventListener(AUTHENTICATION_EXPIRED_EVENT, listener, {
    once: true,
  });

  expect(hasActiveSession()).toBe(false);
  expect(listener).toHaveBeenCalledOnce();
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
});

test("clears the browser session when server logout cannot be confirmed", async () => {
  sessionStorage.setItem("ict-toolkit-token", "network-failure-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-27T20:00:00Z",
  );
  vi.spyOn(globalThis, "fetch").mockRejectedValue(
    new Error("Network unavailable"),
  );

  await expect(logout()).resolves.toBe(false);
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
  expect(sessionStorage.getItem("ict-toolkit-token-expires-at")).toBeNull();
});

test("rejects a malformed sign-in response without storing credentials", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ token: "unbounded-token" }), { status: 200 }),
  );

  await expect(login("synthetic-user", "synthetic-password")).rejects.toThrow(
    "sign-in response was invalid",
  );
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
});
