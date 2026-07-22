import "@testing-library/jest-dom/vitest";

class MockMap {
  addControl() {}
  remove() {}
}

vi.mock("maplibre-gl", () => ({
  Map: MockMap,
  NavigationControl: class {},
}));
