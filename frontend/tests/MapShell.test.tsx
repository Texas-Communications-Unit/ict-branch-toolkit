import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MapShell } from "../src/MapShell";
import type { Incident, RadioSite } from "../src/types";

const api = vi.hoisted(() => ({
  createManualRing: vi.fn(),
  createRadioSite: vi.fn(),
  createSiteAssignment: vi.fn(),
  deleteSiteAssignment: vi.fn(),
  downloadSpatialExport: vi.fn(),
  getFccMapFeatures: vi.fn(),
  getFccTowerDetails: vi.fn(),
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
  api.deleteSiteAssignment.mockResolvedValue(undefined);
  api.getFccMapFeatures.mockResolvedValue({
    count: 0,
    feature_count: 0,
    truncated: false,
    results: [],
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

test("loads FCC towers by map bounds and exposes license details without map interaction", async () => {
  const user = userEvent.setup();
  const tower = {
    id: "tower-1",
    registration_number: "1234567",
    status_code: "C",
    owner_name: "Synthetic County",
    owner_frn: "",
    structure_type: "GTOWER",
    latitude: "33.2000000",
    longitude: "-97.1000000",
    overall_height_m: "120.000",
    faa_study_number: "",
    fcc_record_url: "https://wireless2.fcc.gov/synthetic-asr",
    batch: {
      id: "asr-batch-1",
      dataset: "asr",
      dataset_label: "Antenna Structure Registration",
      archive_kind: "complete",
      archive_name: "r_tower.zip",
      source_url: "https://example.invalid/r_tower.zip",
      content_sha256: "a".repeat(64),
      parser_version: "test",
      retrieved_at: "2026-08-21T12:00:00Z",
    },
  };
  api.getFccMapFeatures.mockResolvedValue({
    count: 1,
    feature_count: 1,
    truncated: false,
    results: [
      {
        kind: "tower",
        key: tower.id,
        latitude: Number(tower.latitude),
        longitude: Number(tower.longitude),
        count: 1,
        tower,
      },
    ],
  });
  api.getFccTowerDetails.mockResolvedValue({
    structure: tower,
    license_count: 1,
    truncated: false,
    disclaimer: "FCC reference data does not authorize transmission.",
    licenses: [
      {
        id: "license-1",
        call_sign: "WQTEST1",
        license_status: "A",
        radio_service_code: "PW",
        licensee_name: "Synthetic County",
        frn: "",
        grant_date: null,
        expiration_date: null,
        fcc_record_url: "https://wireless2.fcc.gov/synthetic-license",
        batch: tower.batch,
        tower_locations: [
          {
            location_number: 1,
            location_type_code: "F",
            location_class_code: "",
            address: "",
            city: "Denton",
            county: "Denton",
            state: "TX",
            latitude: tower.latitude,
            longitude: tower.longitude,
            ground_elevation_m: null,
            asr_registration_number: tower.registration_number,
            structure_type: tower.structure_type,
            frequencies: [
              {
                antenna_number: 1,
                station_class_code: "FB2",
                frequency_hz: 155000000,
                output_power_w: null,
                effective_radiated_power_w: null,
                number_of_units: null,
              },
            ],
            emissions: [
              {
                antenna_number: 1,
                frequency_hz: 155000000,
                emission_designator: "11K2F3E",
              },
            ],
          },
        ],
      },
    ],
  });
  render(<MapShell incident={incident} />);

  await user.click(screen.getByRole("button", { name: "Turn on FCC towers" }));
  expect(
    await screen.findByRole("button", { name: /ASR 1234567/ }),
  ).toBeInTheDocument();
  expect(api.getFccMapFeatures).toHaveBeenCalledWith(
    expect.objectContaining({ west: "-98", east: "-96", zoom: "7" }),
  );

  await user.click(screen.getByRole("button", { name: /ASR 1234567/ }));
  expect(
    await screen.findByText("WQTEST1 — Synthetic County"),
  ).toBeInTheDocument();
  expect(screen.getByText(/155\.000000 MHz/)).toBeInTheDocument();
  expect(
    screen.getByText(/does not authorize transmission/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Open this structure in FCC ASR" }),
  ).toHaveAttribute("href", tower.fcc_record_url);
});

test("renders clustered FCC structures and exposes accessible zoom control", async () => {
  const user = userEvent.setup();
  api.getFccMapFeatures.mockResolvedValue({
    count: 42,
    feature_count: 1,
    truncated: false,
    results: [
      {
        kind: "cluster",
        key: "cluster-1",
        latitude: 33.2,
        longitude: -97.1,
        count: 42,
        tower: null,
      },
    ],
  });
  render(<MapShell incident={incident} />);

  await user.click(screen.getByRole("button", { name: "Turn on FCC towers" }));

  expect(
    await screen.findByRole("button", {
      name: "Zoom to 42 clustered structures",
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "1 map symbol representing 42 FCC structures",
  );
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

test("requires confirmation before removing a visible assignment link", async () => {
  const user = userEvent.setup();
  vi.spyOn(window, "confirm").mockReturnValue(false);
  api.listRadioSites.mockResolvedValue([site]);
  api.listPlans.mockResolvedValue([
    {
      id: "plan-map-1",
      incident: incident.id,
      operational_period: "period-map-1",
      title: "Synthetic ICS-205",
      revisions: [
        {
          id: "revision-map-1",
          status: "draft",
          assignments: [],
        },
      ],
    },
  ]);
  api.listSiteAssignments.mockResolvedValue([
    {
      id: "site-assignment-map-1",
      site: site.id,
      site_name: site.name,
      assignment: "assignment-map-1",
      assignment_label: "1. Command — SYN CALL",
      site_snapshot: {},
    },
  ]);

  render(<MapShell incident={incident} />);
  await user.click(
    await screen.findByRole("button", {
      name: "Remove 1. Command — SYN CALL from Synthetic Command Site",
    }),
  );

  expect(window.confirm).toHaveBeenCalledWith(
    "Remove the link between Synthetic Command Site and 1. Command — SYN CALL? The site and assignment will remain available.",
  );
  expect(api.deleteSiteAssignment).not.toHaveBeenCalled();
});

test("removes a confirmed assignment link and retains both linked records", async () => {
  const user = userEvent.setup();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  api.listRadioSites.mockResolvedValue([site]);
  api.listPlans.mockResolvedValue([
    {
      id: "plan-map-1",
      incident: incident.id,
      operational_period: "period-map-1",
      title: "Synthetic ICS-205",
      revisions: [
        {
          id: "revision-map-1",
          status: "draft",
          assignments: [],
        },
      ],
    },
  ]);
  api.listSiteAssignments.mockResolvedValue([
    {
      id: "site-assignment-map-1",
      site: site.id,
      site_name: site.name,
      assignment: "assignment-map-1",
      assignment_label: "1. Command — SYN CALL",
      site_snapshot: {},
    },
  ]);

  render(<MapShell incident={incident} />);
  await user.click(
    await screen.findByRole("button", {
      name: "Remove 1. Command — SYN CALL from Synthetic Command Site",
    }),
  );

  await waitFor(() =>
    expect(api.deleteSiteAssignment).toHaveBeenCalledWith(
      "site-assignment-map-1",
    ),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Removed the link between Synthetic Command Site and 1. Command — SYN CALL.",
  );
});
