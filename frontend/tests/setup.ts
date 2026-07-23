import "@testing-library/jest-dom/vitest";

class MockMap {
  addControl() {}
  addLayer() {}
  addSource() {}
  fitBounds() {}
  flyTo() {}
  getSource() {
    return undefined;
  }
  loaded() {
    return true;
  }
  on() {}
  once(_event: string, callback: () => void) {
    callback();
  }
  remove() {}
  setStyle() {}
}

class MockMarker {
  setLngLat() {
    return this;
  }
  setPopup() {
    return this;
  }
  addTo() {
    return this;
  }
  on() {
    return this;
  }
  remove() {}
  getLngLat() {
    return { lat: 33.2145, lng: -97.1331 };
  }
}

class MockPopup {
  setText() {
    return this;
  }
}

class MockBounds {
  extend() {
    return this;
  }
}

vi.mock("maplibre-gl", () => ({
  Map: MockMap,
  Marker: MockMarker,
  Popup: MockPopup,
  LngLatBounds: MockBounds,
  NavigationControl: class {},
}));
