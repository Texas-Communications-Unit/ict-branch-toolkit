import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "../src/App";

beforeEach(() => {
  sessionStorage.clear();
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
});

test("signs in and lists incidents from the API", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, options) => {
    const url = String(input);
    if (url.endsWith("/api/auth/token/")) {
      return new Response(JSON.stringify({ token: "test-token" }), {
        status: 200,
      });
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
  expect(screen.getByTestId("map")).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Channel library" }),
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
  await userEvent.click(
    screen.getByRole("button", { name: "Validate dry run" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Validation passed",
  );
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
