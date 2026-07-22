import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "../src/App";

beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

test("signs in and lists incidents from the API", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch");
  fetchMock
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ token: "test-token" }), { status: 200 }),
    )
    .mockResolvedValueOnce(
      new Response(
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
            },
          ],
        }),
        { status: 200 },
      ),
    );

  render(<App />);
  await userEvent.type(screen.getByLabelText("Username"), "admin");
  await userEvent.type(screen.getByLabelText("Password"), "local-password");
  await userEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Synthetic Exercise" }),
    ).toBeInTheDocument(),
  );
  expect(sessionStorage.getItem("ict-toolkit-token")).toBe("test-token");
  expect(screen.getByTestId("map")).toBeInTheDocument();
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
