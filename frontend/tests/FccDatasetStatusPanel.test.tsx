import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { FccDatasetStatusPanel } from "../src/FccDatasetStatusPanel";
import type { FccDatasetStatus } from "../src/types";

const api = vi.hoisted(() => ({ getFccDatasetStatus: vi.fn() }));
vi.mock("../src/api", () => api);

const fixture: FccDatasetStatus = {
  generated_at: "2026-11-04T12:00:00Z",
  datasets: [
    {
      dataset: "asr",
      label: "Antenna Structure Registration",
      status: "available",
      retrieved_at: "2026-10-27T12:00:00Z",
      imported_at: "2026-10-27T12:00:00Z",
      retrieved_age_days: 8,
      timestamp_warning: false,
      last_checked_at: null,
      record_counts: { antenna_structures: 12000 },
      archive_name: "r_tower.zip",
      source_url: "https://data.fcc.gov/download/pub/uls/complete/r_tower.zip",
      content_sha256: "a".repeat(64),
      parser_version: "synthetic-v1",
    },
  ],
};

test("shows import age, retained counts, and keyboard-accessible provenance", async () => {
  api.getFccDatasetStatus.mockResolvedValue(fixture);
  render(<FccDatasetStatusPanel />);
  expect(
    await screen.findByText("Archive retrieved 8 days ago."),
  ).toBeInTheDocument();
  expect(screen.getByText((12000).toLocaleString())).toBeInTheDocument();
  expect(
    screen.getByText(/last source check is not recorded/),
  ).toBeInTheDocument();
  const user = userEvent.setup();
  screen.getByText("Import provenance").focus();
  await user.keyboard("{Enter}");
  expect(
    screen.getByRole("link", { name: "Official FCC complete archive" }),
  ).toHaveAttribute("href", fixture.datasets[0].source_url);
});

test("renders missing, conflicting, and future-date states without claiming freshness", async () => {
  api.getFccDatasetStatus.mockResolvedValue({
    ...fixture,
    datasets: [
      { ...fixture.datasets[0], dataset: "asr", status: "not_imported" },
      {
        ...fixture.datasets[0],
        dataset: "uls_private",
        label: "ULS private",
        status: "ambiguous",
      },
      {
        ...fixture.datasets[0],
        dataset: "uls_commercial",
        label: "ULS commercial",
        timestamp_warning: true,
        retrieved_age_days: null,
      },
    ],
  });
  render(<FccDatasetStatusPanel />);
  expect(await screen.findByText(/No current import/)).toBeInTheDocument();
  expect(
    screen.getByText(/Multiple imports are marked current/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Future import or retrieval date/),
  ).toBeInTheDocument();
  expect(screen.queryByText(/null days/)).not.toBeInTheDocument();
});

test("failed fetch can be retried without losing the panel", async () => {
  api.getFccDatasetStatus
    .mockRejectedValueOnce(new Error("synthetic failure"))
    .mockResolvedValue(fixture);
  render(<FccDatasetStatusPanel />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "FCC search is still available",
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Retry dataset status" }),
  );
  expect(
    await screen.findByText("Archive retrieved 8 days ago."),
  ).toBeInTheDocument();
});

test("a response after unmount does not announce stale status", async () => {
  let finish: (value: FccDatasetStatus) => void = () => undefined;
  api.getFccDatasetStatus.mockReturnValue(
    new Promise<FccDatasetStatus>((resolve) => {
      finish = resolve;
    }),
  );
  const panel = render(<FccDatasetStatusPanel />);
  panel.unmount();
  finish(fixture);
  await waitFor(() =>
    expect(screen.queryByText("Current local import")).not.toBeInTheDocument(),
  );
});
