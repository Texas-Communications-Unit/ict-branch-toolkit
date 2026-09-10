import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FccReferenceWorkspace } from "../src/FccReferenceWorkspace";

const api = vi.hoisted(() => ({
  searchFccAntennaStructures: vi.fn(),
  searchFccLicenses: vi.fn(),
}));

vi.mock("../src/api", () => api);

test("searches licenses and shows provenance and decision-support notice", async () => {
  api.searchFccLicenses.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: "license-1",
        call_sign: "WQTEST1",
        license_status: "A",
        radio_service_code: "PW",
        licensee_name: "Synthetic County",
        frn: "",
        city: "Denton",
        state: "TX",
        expiration_date: null,
        location_count: 1,
        frequency_count: 1,
        frequencies_hz: [155000000],
        nifog_frequency_matches: [],
        batch: {
          id: "batch-1",
          dataset: "uls_private",
          dataset_label: "ULS private land mobile",
          archive_kind: "complete",
          archive_name: "l_LMpriv.zip",
          source_url: "https://example.invalid",
          content_sha256: "a".repeat(64),
          parser_version: "test",
          retrieved_at: "2026-08-20T12:00:00Z",
        },
      },
    ],
  });
  const user = userEvent.setup();
  render(<FccReferenceWorkspace />);

  await user.type(screen.getByLabelText("Search term"), "WQTEST1");
  await user.click(screen.getByRole("button", { name: "Search FCC records" }));

  expect(await screen.findByText(/WQTEST1/)).toBeInTheDocument();
  expect(screen.getByText(/155\.000000 MHz/)).toBeInTheDocument();
  expect(
    screen.getByText(/does not authorize frequency use/),
  ).toBeInTheDocument();
});

test("shows every exact NIFOG identifier with source version and non-color semantics", async () => {
  api.searchFccLicenses.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      {
        id: "license-2",
        call_sign: "WQTEST2",
        license_status: "A",
        radio_service_code: "PW",
        licensee_name: "Synthetic Interop Agency",
        frn: "",
        city: "Synthetic City",
        state: "TX",
        expiration_date: null,
        location_count: 1,
        frequency_count: 1,
        frequencies_hz: [159472500],
        nifog_frequency_matches: [
          {
            frequency_hz: 159472500,
            matches: [
              {
                identifier: "SYN-A",
                name: "Synthetic Interop A",
                matched_roles: ["rx", "tx"],
                channel_rx_frequency_hz: 159472500,
                channel_tx_frequency_hz: 159472500,
                source: {
                  slug: "synthetic-nifog",
                  name: "Synthetic NIFOG",
                  authoritative_url: "https://example.invalid/nifog",
                },
                release: {
                  id: "11111111-1111-1111-1111-111111111111",
                  version: "SYN-2",
                  released_on: null,
                  document_title: "Synthetic NIFOG",
                  publisher: "Synthetic CISA fixture",
                  retrieved_on: null,
                  content_sha256: "b".repeat(64),
                },
              },
              {
                identifier: "SYN-B",
                name: "Synthetic Interop B",
                matched_roles: ["rx"],
                channel_rx_frequency_hz: 159472500,
                channel_tx_frequency_hz: 151000000,
                source: {
                  slug: "synthetic-nifog",
                  name: "Synthetic NIFOG",
                  authoritative_url: "https://example.invalid/nifog",
                },
                release: {
                  id: "11111111-1111-1111-1111-111111111111",
                  version: "SYN-2",
                  released_on: null,
                  document_title: "Synthetic NIFOG",
                  publisher: "Synthetic CISA fixture",
                  retrieved_on: null,
                  content_sha256: "b".repeat(64),
                },
              },
            ],
          },
        ],
        batch: {
          id: "batch-2",
          dataset: "uls_private",
          dataset_label: "ULS private land mobile",
          archive_kind: "complete",
          archive_name: "synthetic.zip",
          source_url: "https://example.invalid/fcc",
          content_sha256: "a".repeat(64),
          parser_version: "test",
          retrieved_at: "2026-09-10T12:00:00Z",
        },
      },
    ],
  });
  const user = userEvent.setup();
  render(<FccReferenceWorkspace />);

  await user.type(screen.getByLabelText("Search term"), "WQTEST2");
  await user.click(screen.getByRole("button", { name: "Search FCC records" }));

  const match = await screen.findByLabelText(
    /NIFOG exact-frequency match for 159\.472500 megahertz/,
  );
  expect(match).toHaveTextContent("Interoperability reference match");
  expect(match).toHaveTextContent("SYN-A, SYN-B");
  expect(match).toHaveTextContent("Synthetic NIFOG SYN-2");
  expect(match).toHaveTextContent("matched RX/TX");
  expect(match).toHaveTextContent("matched RX");
  expect(match).toHaveTextContent("does not authorize transmission");
});
