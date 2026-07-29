import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "../src/App";

beforeEach(() => {
  sessionStorage.clear();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});

test("presents the approved TX-COMU identity and required attribution", () => {
  render(<App />);

  const loginLogo = screen.getByRole("img", {
    name: "Texas Communications Unit (TX-COMU) logo",
  });
  expect(loginLogo).toBeInTheDocument();
  expect(loginLogo.closest("picture")?.querySelector("source")).toHaveAttribute(
    "srcset",
    "/brand/tx-comu-logo-transparent.svg",
  );
  expect(
    screen.getByRole("heading", { name: "ICT Branch Toolkit" }),
  ).toBeInTheDocument();
  expect(screen.getByText("ICT Toolkit")).toBeInTheDocument();
  expect(
    screen.getByText(/Originally developed by the Texas Communications Unit/),
  ).toHaveTextContent("Licensed under GNU AGPL v3");
  expect(
    screen.getByRole("link", {
      name: "MapLibre and third-party notices",
    }),
  ).toHaveAttribute("href", "/third-party/maplibre-gl-LICENSE.txt");
});

test("signs in and lists incidents from the API", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const url = String(input);
    if (url.endsWith("/api/auth/token/")) {
      return new Response(
        JSON.stringify({
          token: "test-token",
          expires_at: "2099-07-27T20:00:00Z",
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/auth/logout/")) {
      return new Response(null, { status: 204 });
    }
    if (url.endsWith("/api/me/")) {
      return new Response(
        JSON.stringify({
          username: "admin",
          display_name: "Synthetic Administrator",
          role: "administrator",
          permissions: ["incident.create", "library.import"],
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/incidents/")) {
      return new Response(
        JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "1",
              name: "Synthetic Exercise",
              incident_number: "SYN-001",
              status: "planning",
              operational_periods: [],
              archived_at: null,
              permissions: ["incident.view", "period.create", "site.view"],
            },
          ],
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/conventional-channels/")) {
      return new Response(
        JSON.stringify({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: "channel-1",
              identifier: "VTAC17",
              name: "VTAC17",
              channel_use: "Tactical",
              rx_frequency_hz: 161850000,
              mode: "analog_fm",
              restrictions: "Licensing and coordination conditions apply.",
              source_pages: "31",
              release: {
                version: "2.02",
                source: {
                  name: "National Interoperability Field Operations Guide",
                },
              },
            },
          ],
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/trunked-talkgroups/")) {
      return new Response(
        JSON.stringify({
          count: 0,
          next: null,
          previous: null,
          results: [],
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/deconfliction-status/")) {
      return new Response(
        JSON.stringify({
          rule_set_id: "rf-deconfliction",
          rule_set_version: "rf-deconfliction-v2-reviewed",
          approved_for_operational_use: false,
          close_frequency_threshold_hz: 12500,
          rules: [],
          analysis_statuses: [],
          access_code_source_hierarchy: [
            "selected_versioned_channel_definition",
            "approved_subscriber_programming_profile",
          ],
          squelch_rule:
            "CTCSS, DCS, NAC, or equivalent access-code differences never suppress RF-001 or RF-002.",
          disclaimer:
            "Decision support only. Results do not constitute frequency coordination, spectrum authorization, an interference determination, a propagation study, or operational approval. Qualified practitioners must review the results before operational use.",
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/api/channel-imports/") && options?.method === "POST") {
      return new Response(
        JSON.stringify({
          valid: true,
          dry_run: true,
          approval_required: false,
          would_create: { releases: 1 },
          errors: [],
        }),
        { status: 200 },
      );
    }
    return new Response(
      JSON.stringify({ count: 0, next: null, previous: null, results: [] }),
      { status: 200 },
    );
  });

  render(<App />);
  await userEvent.type(screen.getByLabelText("Username"), "admin");
  await userEvent.type(screen.getByLabelText("Password"), "local-password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: /^Synthetic Exercise/ }),
    ).toBeInTheDocument(),
  );
  expect(sessionStorage.getItem("ict-toolkit-token")).toBe("test-token");
  expect(sessionStorage.getItem("ict-toolkit-token-expires-at")).toBe(
    "2099-07-27T20:00:00Z",
  );
  expect(screen.getByTestId("map")).toBeInTheDocument();
  expect(screen.getByTestId("map-provider")).toHaveTextContent(
    "Neutral offline map active",
  );
  expect(
    screen.getByRole("heading", { name: "Channel library" }),
  ).toBeInTheDocument();
  expect(screen.getByText("161.850000 MHz · analog_fm")).toBeInTheDocument();
  const librarySearch = screen.getByLabelText(
    "Search channels, uses, restrictions, or source details",
  );
  await userEvent.type(librarySearch, "VTAC17");
  expect(screen.getByText("161.850000 MHz · analog_fm")).toBeInTheDocument();
  await userEvent.clear(librarySearch);
  await userEvent.type(librarySearch, "no matching channel");
  expect(
    screen.getByText("No conventional channels match this search."),
  ).toBeInTheDocument();
  expect(screen.getByText("Synthetic Administrator")).toBeInTheDocument();
  const workspaceLogo = screen.getByRole("img", {
    name: "Texas Communications Unit (TX-COMU) logo",
  });
  expect(workspaceLogo).toBeInTheDocument();
  expect(
    workspaceLogo.closest("picture")?.querySelector("source"),
  ).toHaveAttribute("srcset", "/brand/tx-comu-logo-transparent.svg");
  expect(screen.getByText("ICT Toolkit")).toBeInTheDocument();
  expect(
    screen.getByText(/TX-COMU names, logos, and identifying marks/),
  ).toHaveTextContent("not relicensed under the software license");
  expect(
    screen.getByRole("link", {
      name: "MapLibre and third-party notices",
    }),
  ).toHaveAttribute("href", "/third-party/maplibre-gl-LICENSE.txt");
  await userEvent.click(
    screen.getByRole("button", { name: "Validate dry run" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Validation passed",
  );
  await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(
    await screen.findByRole("button", { name: "Sign in" }),
  ).toBeInTheDocument();
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
});

test("shows an actionable message when sign-in fails", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("Unauthorized", { status: 400 }),
  );
  render(<App />);
  await userEvent.type(screen.getByLabelText("Username"), "admin");
  await userEvent.type(screen.getByLabelText("Password"), "wrong");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Sign-in failed");
});

test("returns to sign-in when the API rejects an active session", async () => {
  sessionStorage.setItem("ict-toolkit-token", "expired-server-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    "2099-07-27T20:00:00Z",
  );
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "Token has expired." }), {
      status: 401,
    }),
  );

  render(<App />);

  expect(
    await screen.findByRole("button", { name: "Sign in" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Your session expired. Sign in again.",
  );
  expect(sessionStorage.getItem("ict-toolkit-token")).toBeNull();
});
