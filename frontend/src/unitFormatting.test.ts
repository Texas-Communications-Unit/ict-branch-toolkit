import { describe, expect, it } from "vitest";

import {
  formatKilometersAsMiles,
  formatMetersAsFeet,
  formatMetersAsMiles,
} from "./unitFormatting";

describe("US customary companion unit formatting", () => {
  it("converts meters to feet using a stable exact conversion", () => {
    expect(formatMetersAsFeet(100)).toBe("328 ft (100 m)");
    expect(formatMetersAsFeet("30.48")).toBe("100 ft (30.48 m)");
  });

  it("rounds feet to the nearest whole foot at the boundary", () => {
    expect(formatMetersAsFeet(0.1524)).toBe("1 ft (0.152 m)");
    expect(formatMetersAsFeet(0.15)).toBe("0 ft (0.15 m)");
  });

  it("formats meter and kilometer distances as miles without changing source units", () => {
    expect(formatMetersAsMiles(1609.344)).toBe("1.00 mi (1609.344 m)");
    expect(formatKilometersAsMiles(1.609344)).toBe("1.00 mi (1.609 km)");
    expect(formatMetersAsMiles(1)).toBe("0.00 mi (1 m)");
    expect(formatKilometersAsMiles(1609.344)).toBe("1000.00 mi (1609.344 km)");
  });

  it("preserves zero and handles null, blank, and invalid values explicitly", () => {
    expect(formatMetersAsFeet(0)).toBe("0 ft (0 m)");
    expect(formatMetersAsFeet(null)).toBe("Not listed");
    expect(formatMetersAsFeet(undefined)).toBe("Not listed");
    expect(formatMetersAsFeet("")).toBe("Not listed");
    expect(formatMetersAsFeet(Number.NaN)).toBe("Not listed");
    expect(formatMetersAsMiles("unknown")).toBe("Not listed");
  });

  it("formats large heights predictably", () => {
    expect(formatMetersAsFeet(10000)).toBe("32,808 ft (10000 m)");
  });
});
