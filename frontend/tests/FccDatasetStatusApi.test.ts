import { getFccDatasetStatus } from "../src/api";

const fixture = {
  generated_at: "2026-11-04T12:00:00Z",
  datasets: ["asr", "uls_private", "uls_commercial"].map((dataset) => ({
    dataset,
    label: dataset,
    status: "not_imported",
    retrieved_at: null,
    imported_at: null,
    retrieved_age_days: null,
    timestamp_warning: false,
    last_checked_at: null,
    record_counts: {},
    archive_name: null,
    source_url: null,
    content_sha256: null,
    parser_version: null,
  })),
};

beforeEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

test("accepts the three-dataset envelope through the authenticated request helper", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValue(new Response(JSON.stringify(fixture)));
  expect(await getFccDatasetStatus()).toEqual(fixture);
  expect(fetch.mock.calls[0][0]).toMatch(/\/api\/fcc-dataset-status\/$/);
});

test.each([
  {},
  { ...fixture, datasets: [] },
  { ...fixture, generated_at: "invalid date" },
  {
    ...fixture,
    datasets: [fixture.datasets[0], fixture.datasets[0], fixture.datasets[0]],
  },
  {
    ...fixture,
    datasets: [
      { ...fixture.datasets[0], record_counts: null },
      ...fixture.datasets.slice(1),
    ],
  },
])(
  "rejects malformed status responses so the panel can show its retry state",
  async (body) => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(body)),
    );
    await expect(getFccDatasetStatus()).rejects.toThrow(
      "Invalid FCC dataset status response",
    );
  },
);
