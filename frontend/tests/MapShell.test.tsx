import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MapShell } from "../src/MapShell";
import type { Incident, RadioSite } from "../src/types";

const api = vi.hoisted(() => ({
  createManualRing: vi.fn(),
  createRadioSite: vi.fn(),
  createSiteAssignment: vi.fn(),
  downloadSpatialExport: vi.fn(),
  listCoverageEstimates: vi.fn(),
  listDirectionalCoverageAnalyses: vi.fn(),
  listPlans: vi.fn(),
  listRadioSites: vi.fn(),
  listSiteAssignments: vi.fn(),
  parseCoordinate: vi.fn(),
  searchAddress: vi.fn(),
  updateRadioSite: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-map-1",
  name: "Synthetic Map Exercise",
  incident_number: "SYN-MAP",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["site.view", "site.edit", "site.export"],
};

const site: RadioSite = {
  id: "site-map-1",
  incident: incident.id,
  name: "Synthetic Command Site",
  description: "Synthetic test fixture",
  latitude: "31.000000",
  longitude: "-99.000000",
  entered_coordinate: "31.000000, -99.000000",
  coordinate_format: "decimal",
  coordinate_formats: {
    decimal: "31.000000, -99.000000",
    ddm: "31° 00.0000′ N, 99° 00.0000′ W",
    dms: "31° 00′ 00.00″ N, 99° 00′ 00.00″ W",
    mgrs: "14R NV 00000 00000",
  },
  address: "",
  source_identity: "",
  source_retrieved_at: null,
  rings: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listRadioSites.mockResolvedValue([]);
  api.listPlans.mockResolvedValue([]);
  api.listCoverageEstimates.mockResolvedValue([]);
  api.listDirectionalCoverageAnalyses.mockResolvedValue([]);
  api.listSiteAssignments.mockResolvedValue([]);
  api.parseCoordinate.mockResolvedValue({
    latitude: 31,
    longitude: -99,
    input_format: "decimal",
    formats: site.coordinate_formats,
  });
  api.createRadioSite.mockResolvedValue(site);
  api.createManualRing.mockResolvedValue({
    id: "ring-map-1",
    site: site.id,
    ring_type: "operational",
    radius_m: 1_000,
    label: "Synthetic operating area",
  });
});

async function prepareSiteForm(user: ReturnType<typeof userEvent.setup>) {
  render(<MapShell incident={incident} />);
  await user.type(screen.getByLabelText("Site name"), "Synthetic Command Site");
  await user.type(screen.getByLabelText("Coordinate"), "31.000000, -99.000000");
  await user.type(screen.getByLabelText("Description"), "Synthetic fixture");
  await user.click(screen.getByRole("button", { name: "Parse and preview" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Save radio site" }),
    ).toBeEnabled(),
  );
}

test("resets the captured radio-site form only after a successful save", async () => {
  const user = userEvent.setup();
  await prepareSiteForm(user);

  await user.click(screen.getByRole("button", { name: "Save radio site" }));

  await waitFor(() => expect(api.createRadioSite).toHaveBeenCalledTimes(1));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Radio site saved.",
  );
  expect(screen.getByLabelText("Site name")).toHaveValue("");
  expect(screen.getByLabelText("Coordinate")).toHaveValue("");
  expect(screen.getByLabelText("Description")).toHaveValue("");
});

test("retains radio-site form values when the save fails", async () => {
  const user = userEvent.setup();
  api.createRadioSite.mockRejectedValue(
    new Error("Synthetic radio-site save failed."),
  );
  await prepareSiteForm(user);

  await user.click(screen.getByRole("button", { name: "Save radio site" }));

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Synthetic radio-site save failed.",
  );
  expect(api.createRadioSite).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText("Site name")).toHaveValue(
    "Synthetic Command Site",
  );
  expect(screen.getByLabelText("Coordinate")).toHaveValue(
    "31.000000, -99.000000",
  );
});

test("resets the captured manual-ring form only after a successful save", async () => {
  const user = userEvent.setup();
  api.listRadioSites.mockResolvedValue([site]);
  render(<MapShell incident={incident} />);
  const submit = await screen.findByRole("button", { name: "Save ring" });
  const form = submit.closest("form");
  expect(form).not.toBeNull();
  await user.type(within(form!).getByLabelText("Radius in meters"), "1000");
  await user.type(
    within(form!).getByLabelText("Label"),
    "Synthetic operating area",
  );

  await user.click(submit);

  await waitFor(() => expect(api.createManualRing).toHaveBeenCalledTimes(1));
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Manual planning ring saved.",
  );
  expect(within(form!).getByLabelText("Radius in meters")).toHaveValue(null);
  expect(within(form!).getByLabelText("Label")).toHaveValue("");
});

test("retains manual-ring form values when the save fails", async () => {
  const user = userEvent.setup();
  api.listRadioSites.mockResolvedValue([site]);
  api.createManualRing.mockRejectedValue(
    new Error("Synthetic manual-ring save failed."),
  );
  render(<MapShell incident={incident} />);
  const submit = await screen.findByRole("button", { name: "Save ring" });
  const form = submit.closest("form");
  expect(form).not.toBeNull();
  await user.type(within(form!).getByLabelText("Radius in meters"), "1000");
  await user.type(
    within(form!).getByLabelText("Label"),
    "Synthetic operating area",
  );

  await user.click(submit);

  expect(await screen.findByRole("status")).toHaveTextContent(
    "Synthetic manual-ring save failed.",
  );
  expect(api.createManualRing).toHaveBeenCalledTimes(1);
  expect(within(form!).getByLabelText("Radius in meters")).toHaveValue(1000);
  expect(within(form!).getByLabelText("Label")).toHaveValue(
    "Synthetic operating area",
  );
});
