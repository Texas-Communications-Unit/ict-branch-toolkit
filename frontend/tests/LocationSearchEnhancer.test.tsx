import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LocationSearchEnhancer } from "../src/LocationSearchEnhancer";

const api = vi.hoisted(() => ({ resolveLocation: vi.fn() }));
vi.mock("../src/locationSearchApi", () => api);

function mapFixture() {
  document.body.innerHTML = `
    <div id="root"></div>
    <section class="map-panel" aria-labelledby="map-heading">
      <h2 id="map-heading">Radio site planning</h2>
      <label>Coordinate <input placeholder="33.214500, -97.133100" /></label>
      <button type="button">Parse and preview</button>
    </section>
  `;
}

afterEach(() => {
  document.body.innerHTML = "";
  vi.clearAllMocks();
});

test("resolves locally with external lookup disabled and exposes a textual result list", async () => {
  mapFixture();
  api.resolveLocation.mockResolvedValue({
    original_query: "33.2145, -97.1331",
    resolution_method: "local_coordinate",
    external_lookup_performed: false,
    provider: "local-coordinate-parser",
    configured: true,
    results: [
      {
        label: "33.214500, -97.133100",
        latitude: 33.2145,
        longitude: -97.1331,
        crs: "EPSG:4326",
        provider: "local-coordinate-parser",
        original_query: "33.2145, -97.1331",
        formats: {
          decimal: "33.214500, -97.133100",
          ddm: "33° 12.8700′ N, 97° 07.9860′ W",
          dms: "33° 12′ 52.20″ N, 97° 07′ 59.16″ W",
          mgrs: "14SQA0000000000",
        },
      },
    ],
  });
  const user = userEvent.setup();
  render(<LocationSearchEnhancer />);

  await user.type(screen.getByLabelText("Location"), "33.2145, -97.1331");
  await user.click(screen.getByRole("button", { name: "Resolve location" }));

  expect(api.resolveLocation).toHaveBeenCalledWith("33.2145, -97.1331", false);
  const results = await screen.findByRole("list", {
    name: "Normalized location results",
  });
  expect(results).toBeInTheDocument();
  expect(within(results).getByText(/WGS 84/)).toBeInTheDocument();
});

test("requires an explicit operator choice before external lookup", async () => {
  mapFixture();
  api.resolveLocation.mockResolvedValue({
    original_query: "Alpha Rd & Bravo St",
    resolution_method: "geocoder",
    external_lookup_performed: false,
    provider: "synthetic-test-provider",
    configured: true,
    blocked_reason: "External lookup was not approved for this query.",
    results: [],
  });
  const user = userEvent.setup();
  render(<LocationSearchEnhancer />);

  await user.type(screen.getByLabelText("Location"), "Alpha Rd & Bravo St");
  await user.click(screen.getByRole("button", { name: "Resolve location" }));

  expect(
    await screen.findByText(/External lookup was not approved/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/protected or sensitive operational locations/),
  ).toBeInTheDocument();
});

test("selecting a keyboard-accessible result populates the canonical coordinate field", async () => {
  mapFixture();
  const preview = screen.getByRole("button", { name: "Parse and preview" });
  const clicked = vi.fn();
  preview.addEventListener("click", clicked);
  api.resolveLocation.mockResolvedValue({
    original_query: "Synthetic EOC",
    resolution_method: "geocoder",
    external_lookup_performed: true,
    provider: "synthetic-test-provider",
    configured: true,
    results: [
      {
        label: "Synthetic EOC, Synthetic City, TX",
        latitude: 33.2145,
        longitude: -97.1331,
        crs: "EPSG:4326",
        provider: "synthetic-test-provider",
        original_query: "Synthetic EOC",
        formats: {
          decimal: "33.214500, -97.133100",
          ddm: "",
          dms: "",
          mgrs: "",
        },
      },
    ],
  });
  const user = userEvent.setup();
  render(<LocationSearchEnhancer />);

  await user.type(screen.getByLabelText("Location"), "Synthetic EOC");
  await user.click(
    screen.getByRole("checkbox", {
      name: /Allow this query to be sent to the configured external location provider/,
    }),
  );
  await user.click(screen.getByRole("button", { name: "Resolve location" }));
  await user.click(
    await screen.findByRole("button", {
      name: /Synthetic EOC, Synthetic City, TX/,
    }),
  );
  await act(async () => Promise.resolve());

  expect(
    document.querySelector<HTMLInputElement>(
      'input[placeholder="33.214500, -97.133100"]',
    )?.value,
  ).toBe("33.214500, -97.133100");
  expect(clicked).toHaveBeenCalled();
  expect(screen.getByRole("status")).toHaveTextContent(
    /sent to the existing map preview workflow/,
  );
});
