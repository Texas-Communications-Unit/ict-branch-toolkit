import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AssetManagementWorkspace } from "../src/AssetManagementWorkspace";
import type {
  AssetCheckout,
  CurrentUser,
  Incident,
  InventoryAsset,
} from "../src/types";

const api = vi.hoisted(() => ({
  checkoutInventoryAsset: vi.fn(),
  createChargingRecord: vi.fn(),
  createInventoryAsset: vi.fn(),
  createMaintenanceRecord: vi.fn(),
  createProgrammingRecord: vi.fn(),
  listAssetCheckouts: vi.fn(),
  listChargingRecords: vi.fn(),
  listInventoryAssets: vi.fn(),
  listMaintenanceRecords: vi.fn(),
  listProgrammingRecords: vi.fn(),
  resolveInventoryHold: vi.fn(),
  returnInventoryAsset: vi.fn(),
  updateInventoryAsset: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-assets-1",
  name: "Synthetic Asset Exercise",
  incident_number: "SYN-ASSET-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["inventory.view", "inventory.manage"],
};

const manager: CurrentUser = {
  username: "asset-manager",
  display_name: "Asset Manager",
  role: "coml",
  permissions: ["inventory.view", "inventory.manage"],
};

const radio: InventoryAsset = {
  id: "radio-1",
  asset_id: "RADIO-12000",
  category: "radio",
  parent: null,
  manufacturer: "Synthetic",
  model: "Portable",
  serial_number: "TEST-1",
  alias: "Exercise radio",
  asset_subtype: "handheld",
  flash_code: "",
  subscriber_id: "",
  system_ids: "",
  acquisition_date: null,
  last_calibrated_at: null,
  status: "checked_out",
  notes: "",
  created_by_username: manager.username,
  created_at: "2026-08-22T12:00:00Z",
  updated_at: "2026-08-22T12:00:00Z",
};

const checkout: AssetCheckout = {
  id: "checkout-1",
  incident: incident.id,
  asset: radio.id,
  asset_detail: radio,
  assigned_name: "Synthetic Assignee",
  assigned_organization: "Synthetic County",
  point_of_contact: "",
  phone_number: "",
  mailing_address: "",
  assignment_notes: "",
  driver_license_jurisdiction: "TX",
  driver_license_number: "12345678",
  driver_license_last_four: "5678",
  state: "active",
  checked_out_by_username: manager.username,
  checked_out_at: "2026-08-22T12:00:00Z",
  returned_by_username: null,
  returned_at: null,
  return_condition: "",
  hold_reason: "",
  hold_resolved_by_username: null,
  hold_resolved_at: null,
  hold_resolution_note: "",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listInventoryAssets.mockResolvedValue([radio]);
  api.listAssetCheckouts.mockResolvedValue([checkout]);
  api.listProgrammingRecords.mockResolvedValue([]);
  api.listMaintenanceRecords.mockResolvedValue([]);
  api.listChargingRecords.mockResolvedValue([]);
  api.returnInventoryAsset.mockResolvedValue({
    ...checkout,
    state: "returned",
    driver_license_number: null,
  });
});

test("shows incident-authorized license data and uses an accessible return workflow", async () => {
  const user = userEvent.setup();
  render(
    <AssetManagementWorkspace incident={incident} currentUser={manager} />,
  );

  expect(await screen.findByText("DL: TX 12345678")).toBeInTheDocument();
  await user.click(
    screen.getByRole("button", { name: "Record return or exception" }),
  );
  expect(
    screen.getByRole("heading", { name: "Record return for RADIO-12000" }),
  ).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Condition"), "damaged");
  await user.type(
    screen.getByLabelText("Incident report or accountability-hold reason"),
    "Synthetic cracked display report.",
  );
  await user.click(screen.getByRole("button", { name: "Save return" }));

  expect(api.returnInventoryAsset).toHaveBeenCalledWith("checkout-1", {
    condition: "damaged",
    hold_reason: "Synthetic cracked display report.",
  });
});
