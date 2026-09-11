import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NifogResourceCategories } from "./NifogResourceCategories";
import type { ConventionalChannel, ResourceRelease } from "./types";

const release: ResourceRelease = {
  id: "release-nifog",
  source: {
    id: "source-nifog",
    slug: "synthetic-nifog",
    name: "Synthetic NIFOG",
    source_type: "cisa_nifog",
    authoritative_url: "https://example.invalid/nifog",
  },
  version: "SYN-2026",
  released_on: "2026-01-01",
  effective_status: "effective",
  content_sha256: "0".repeat(64),
  document_title: "Synthetic interoperability guide",
  publisher: "Synthetic publisher",
  retrieved_on: "2026-01-02",
  permitted_use: "Synthetic fixture only",
  transformation_method: "Synthetic fixture",
  imported_at: "2026-01-02T00:00:00Z",
};

function channel(overrides: Partial<ConventionalChannel>): ConventionalChannel {
  return {
    id: "channel-1",
    release,
    identifier: "VTAC11",
    name: "VTAC11",
    channel_use: "Tactical simplex",
    band: "VHF",
    jurisdiction: "National",
    rx_frequency_hz: 151_137_500,
    tx_frequency_hz: 151_137_500,
    bandwidth_hz: 12_500,
    mode: "analog_fm",
    rx_squelch: "156.7",
    tx_squelch: "156.7",
    emission_designator: "11K2F3E",
    eligibility: "Synthetic eligible users",
    authorization: "Authorization required",
    source_section: "VHF Tactical Simplex – VCALL & VTAC",
    source_pages: "29",
    restrictions: "Synthetic restriction",
    notes: "Synthetic note",
    is_active: true,
    ...overrides,
  };
}

describe("categorized NIFOG resources", () => {
  it("groups by imported source section and keeps disclosures independently operable", () => {
    render(
      <NifogResourceCategories
        channels={[
          channel({ id: "one" }),
          channel({ id: "two", identifier: "VTAC12", name: "VTAC12" }),
          channel({
            id: "three",
            identifier: "8CALL90",
            name: "8CALL90",
            source_section: "800 MHz Calling Channels",
            source_pages: "46",
          }),
        ]}
      />,
    );

    const vhfSummary = screen
      .getByText("VHF Tactical Simplex – VCALL & VTAC")
      .closest("summary");
    const eightHundredSummary = screen
      .getByText("800 MHz Calling Channels")
      .closest("summary");
    const vhf = vhfSummary?.closest("details");
    const eightHundred = eightHundredSummary?.closest("details");

    expect(vhf).not.toHaveAttribute("open");
    expect(eightHundred).not.toHaveAttribute("open");
    fireEvent.click(vhfSummary!);
    fireEvent.click(eightHundredSummary!);
    expect(vhf).toHaveAttribute("open");
    expect(eightHundred).toHaveAttribute("open");
  });

  it("renders exact technical fields, source version, and authorization warning", () => {
    render(<NifogResourceCategories channels={[channel({})]} />);
    const summary = screen
      .getByText("VHF Tactical Simplex – VCALL & VTAC")
      .closest("summary");
    fireEvent.click(summary!);

    expect(screen.getAllByText("151.137500 MHz")).toHaveLength(2);
    expect(screen.getAllByText("156.7")).toHaveLength(2);
    expect(screen.getByText("11K2F3E")).toBeInTheDocument();
    expect(
      screen.getByText(/Synthetic NIFOG · release SYN-2026 · page\(s\) 29/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/does not itself authorize transmission/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("columnheader", { name: "Mobile RX Frequency" }),
    ).toBeInTheDocument();
  });

  it("preserves non-NIFOG conventional records in a separate disclosure", () => {
    const localRelease: ResourceRelease = {
      ...release,
      id: "release-local",
      source: {
        ...release.source,
        id: "source-local",
        source_type: "local",
        name: "Synthetic local source",
      },
    };
    render(
      <NifogResourceCategories
        channels={[
          channel({
            id: "local-channel",
            release: localRelease,
            identifier: "LOCAL-1",
            name: "Synthetic Local Channel",
          }),
        ]}
      />,
    );

    expect(
      screen.getByText("Other conventional reference channels"),
    ).toBeInTheDocument();
    expect(screen.getByText("Synthetic Local Channel")).toBeInTheDocument();
  });
});
