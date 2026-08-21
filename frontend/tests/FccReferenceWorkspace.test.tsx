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
