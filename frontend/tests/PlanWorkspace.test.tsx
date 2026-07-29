import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { PlanWorkspace } from "../src/PlanWorkspace";
import type { CollaborationChange, ICS205Plan, Incident } from "../src/types";

const api = vi.hoisted(() => ({
  approvePlanRevision: vi.fn(),
  collaborationDeviceId: vi.fn(() => "00000000-0000-4000-8000-000000000001"),
  comparePlanRevisions: vi.fn(),
  copyPlanRevision: vi.fn(),
  createPlan: vi.fn(),
  createPlanRelationship: vi.fn(),
  downloadPlanPdf: vi.fn(),
  heartbeatCollaborationPresence: vi.fn(),
  listCollaborationChanges: vi.fn(),
  listCollaborationPresence: vi.fn(),
  listPlans: vi.fn(),
  releaseCollaborationPresence: vi.fn(),
  resolveCollaborationConflict: vi.fn(),
  sendCollaborationMutation: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-collaboration-1",
  name: "Synthetic Collaboration Exercise",
  incident_number: "SYN-COLLAB",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["plan.view", "plan.edit", "plan.approve", "plan.export"],
};

const plan: ICS205Plan = {
  id: "plan-collaboration-1",
  incident: incident.id,
  operational_period: "period-1",
  title: "Synthetic ICS-205",
  revisions: [
    {
      id: "revision-collaboration-1",
      plan: "plan-collaboration-1",
      number: 1,
      status: "draft",
      is_locked: false,
      prepared_by_name: "",
      prepared_by_position: "",
      approved_at: null,
      collaboration_version: 3,
      assignments: [
        {
          id: "assignment-collaboration-1",
          revision: "revision-collaboration-1",
          position: 1,
          function: "Command",
          channel_name: "SYN CALL",
          assignment: "Synthetic exercise",
          rx_frequency_hz: 155_000_000,
          rx_squelch: "",
          tx_frequency_hz: 155_000_000,
          tx_squelch: "",
          mode: "Analog FM",
          remarks: "Saved first",
          structured_note: "",
          collaboration_version: 2,
          resource_snapshot: { source: "synthetic" },
        },
      ],
      relationships: [],
    },
  ],
};

const conflict: CollaborationChange = {
  id: "change-conflict-1",
  client_mutation_id: "00000000-0000-4000-8000-000000000010",
  revision: "revision-collaboration-1",
  actor: 2,
  device_id: "00000000-0000-4000-8000-000000000001",
  operation: "assignment.update",
  object_id: "assignment-collaboration-1",
  section: "ics205",
  base_version: 1,
  resulting_version: null,
  affected_fields: ["remarks"],
  proposed_snapshot: { remarks: "Retained proposal" },
  current_snapshot: {
    remarks: "Saved first",
    collaboration_version: 2,
  },
  payload_sha256: "a".repeat(64),
  disposition: "conflict",
  result: {
    detail: "The saved record changed after this editor loaded it.",
  },
  resolution: null,
  created_at: "2026-07-28T23:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  api.listPlans.mockResolvedValue([plan]);
  api.heartbeatCollaborationPresence.mockResolvedValue({
    id: "presence-1",
    revision: "revision-collaboration-1",
    device_id: "00000000-0000-4000-8000-000000000001",
    section: "ics205",
    mode: "editing",
    sequence: 1,
    expires_at: "2026-07-28T23:01:15Z",
    last_seen_at: "2026-07-28T23:00:00Z",
    display_name: "Synthetic COML",
    is_current_user: true,
  });
  api.listCollaborationPresence.mockResolvedValue([
    {
      id: "presence-1",
      revision: "revision-collaboration-1",
      device_id: "00000000-0000-4000-8000-000000000001",
      section: "ics205",
      mode: "editing",
      sequence: 1,
      expires_at: "2026-07-28T23:01:15Z",
      last_seen_at: "2026-07-28T23:00:00Z",
      display_name: "Synthetic COML",
      is_current_user: true,
    },
  ]);
  api.listCollaborationChanges.mockResolvedValue([conflict]);
  api.releaseCollaborationPresence.mockResolvedValue(undefined);
  api.resolveCollaborationConflict.mockResolvedValue({
    ...conflict,
    resolution: {
      id: "resolution-1",
      decision: "replace",
      explanation: "User intentionally applied the retained proposed values.",
      replacement_change: "change-saved-2",
      resolved_by: 2,
      created_at: "2026-07-28T23:01:00Z",
    },
  });
});

test("shows presence and requires an explicit conflict decision", async () => {
  const user = userEvent.setup();
  api.sendCollaborationMutation.mockResolvedValue({
    ...conflict,
    id: "change-saved-2",
    client_mutation_id: "00000000-0000-4000-8000-000000000011",
    base_version: 2,
    resulting_version: 3,
    disposition: "saved",
    current_snapshot: {
      remarks: "Saved first",
      collaboration_version: 2,
    },
    result: { assignment: "assignment-collaboration-1", version: 3 },
  });

  render(<PlanWorkspace incident={incident} />);

  expect(
    await screen.findByText(/Synthetic COML \(you\): editing/i),
  ).toBeInTheDocument();
  const panel = screen.getByRole("region", {
    name: "Resolve concurrent change",
  });
  expect(
    within(panel).getByText(/"remarks": "Retained proposal"/i),
  ).toBeInTheDocument();
  expect(
    within(panel).getByText(/"remarks": "Saved first"/i),
  ).toBeInTheDocument();

  await user.click(
    within(panel).getByRole("button", { name: "Apply my proposed values" }),
  );

  await waitFor(() =>
    expect(api.sendCollaborationMutation).toHaveBeenCalledWith(
      expect.objectContaining({
        operation: "assignment.update",
        object_id: "assignment-collaboration-1",
        base_version: 2,
        changes: { remarks: "Retained proposal" },
      }),
    ),
  );
  expect(api.resolveCollaborationConflict).toHaveBeenCalledWith(
    "change-conflict-1",
    {
      decision: "replace",
      explanation: "User intentionally applied the retained proposed values.",
      replacement_change: "change-saved-2",
    },
  );
});

test("submits a new assignment with the loaded revision version", async () => {
  const user = userEvent.setup();
  api.listCollaborationChanges.mockResolvedValue([]);
  api.sendCollaborationMutation.mockResolvedValue({
    ...conflict,
    id: "change-saved-create",
    operation: "assignment.create",
    object_id: null,
    base_version: 3,
    resulting_version: 4,
    proposed_snapshot: {},
    current_snapshot: {},
    disposition: "saved",
    result: {
      assignment: "assignment-collaboration-2",
      version: 1,
      revision_version: 4,
    },
  });

  render(<PlanWorkspace incident={incident} />);
  const form = await screen.findByRole("button", {
    name: "Insert assignment row",
  });
  const assignmentForm = form.closest("form");
  expect(assignmentForm).not.toBeNull();
  await user.type(
    within(assignmentForm!).getByRole("textbox", { name: "Function" }),
    "Tactical",
  );
  await user.type(
    within(assignmentForm!).getByRole("textbox", {
      name: "Channel or talkgroup",
    }),
    "SYN TAC",
  );
  await user.click(form);

  await waitFor(() =>
    expect(api.sendCollaborationMutation).toHaveBeenCalledWith(
      expect.objectContaining({
        operation: "assignment.create",
        revision: "revision-collaboration-1",
        base_version: 3,
        changes: expect.objectContaining({
          position: 2,
          function: "Tactical",
          channel_name: "SYN TAC",
        }),
      }),
    ),
  );
});
