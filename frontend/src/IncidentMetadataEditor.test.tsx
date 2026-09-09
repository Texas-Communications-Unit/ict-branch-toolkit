import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { IncidentMetadataEditor } from "./IncidentMetadataEditor";

const incident = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Synthetic Incdent",
  incident_number: "SYN-121",
  status: "planning" as const,
  operational_periods: [
    {
      id: "22222222-2222-4222-8222-222222222222",
      name: "Operational Period One",
      starts_at: "2026-09-09T13:00:00Z",
      ends_at: "2026-09-09T19:00:00Z",
    },
  ],
  archived_at: null,
  permissions: ["incident.view", "incident.change", "period.change"],
};

function activeSession() {
  sessionStorage.setItem("ict-toolkit-token", "test-token");
  sessionStorage.setItem(
    "ict-toolkit-token-expires-at",
    new Date(Date.now() + 60_000).toISOString(),
  );
}

function mountIncidentPanel() {
  const root = document.createElement("div");
  root.id = "root";
  root.innerHTML = `
    <section class="planning-panel" aria-labelledby="incidents-heading">
      <h2 id="incidents-heading">Incidents</h2>
    </section>
  `;
  document.body.append(root);
}

describe("IncidentMetadataEditor", () => {
  beforeEach(() => {
    activeSession();
    mountIncidentPanel();
  });

  afterEach(() => {
    document.body.innerHTML = "";
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("shows capability-gated current values and saves an incident rename", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          return {
            ok: true,
            status: 200,
            json: async () => ({ ...incident, name: "Synthetic Incident" }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({
            count: 1,
            next: null,
            previous: null,
            results: [incident],
          }),
        } as Response;
      }),
    );

    render(<IncidentMetadataEditor />);

    const name = await screen.findByLabelText("Incident name");
    expect(name).toHaveValue("Synthetic Incdent");
    expect(screen.getByLabelText("Period name")).toHaveValue(
      "Operational Period One",
    );

    fireEvent.change(name, { target: { value: "Synthetic Incident" } });
    fireEvent.click(screen.getByRole("button", { name: "Save incident name" }));

    await screen.findByText("Incident name saved as Synthetic Incident.");
    expect(screen.getByLabelText("Incident name")).toHaveValue(
      "Synthetic Incident",
    );
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining(`/api/incidents/${incident.id}/`),
      expect.objectContaining({ method: "PATCH" }),
    );
  });

  it("presents a clear read-only state without mutation controls", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              ...incident,
              permissions: ["incident.view"],
            },
          ],
        }),
      }),
    );

    render(<IncidentMetadataEditor />);

    await screen.findByText(
      "Your incident role is read-only for incident and operational-period metadata.",
    );
    expect(
      screen.queryByRole("button", { name: "Save incident name" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save operational period" }),
    ).not.toBeInTheDocument();
  });

  it("preserves entered values when server validation fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          return {
            ok: false,
            status: 400,
            text: async () =>
              JSON.stringify({ name: ["Incident name cannot be blank."] }),
          } as Response;
        }
        return {
          ok: true,
          status: 200,
          json: async () => ({
            count: 1,
            next: null,
            previous: null,
            results: [incident],
          }),
        } as Response;
      }),
    );

    render(<IncidentMetadataEditor />);
    const name = await screen.findByLabelText("Incident name");
    fireEvent.change(name, { target: { value: "   " } });
    fireEvent.click(screen.getByRole("button", { name: "Save incident name" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        "name: Incident name cannot be blank.",
      ),
    );
    expect(name).toHaveValue("   ");
  });
});
