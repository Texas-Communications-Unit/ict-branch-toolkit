import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { DeconflictionWorkspace } from "../src/DeconflictionWorkspace";
import type {
  ConventionalChannel,
  DeconflictionAnalysis,
  DeconflictionRuleSetStatus,
  ICS205Plan,
  Incident,
} from "../src/types";

const api = vi.hoisted(() => ({
  approveDeconflictionAnalysis: vi.fn(),
  createDeconflictionAnalysis: vi.fn(),
  createDeconflictionFindingDisposition: vi.fn(),
  getDeconflictionStatus: vi.fn(),
  listConventionalChannels: vi.fn(),
  listDeconflictionAnalyses: vi.fn(),
  listPlans: vi.fn(),
}));

vi.mock("../src/api", () => api);

const incident: Incident = {
  id: "incident-deconfliction-1",
  name: "Synthetic Deconfliction Exercise",
  incident_number: "SYN-DECON-1",
  status: "planning",
  operational_periods: [],
  archived_at: null,
  permissions: ["rf.view", "rf.edit", "rf.approve"],
};

const provisionalStatus: DeconflictionRuleSetStatus = {
  rule_set_id: "rf-deconfliction",
  rule_set_version: "rf-deconfliction-v2-reviewed",
  approved_for_operational_use: false,
  close_frequency_threshold_hz: 12_500,
  rules: [
    {
      id: "RF-001",
      name: "Co-channel overlap",
      severity: "critical",
      summary: "Operating frequencies match and approved areas overlap.",
    },
  ],
  analysis_statuses: [
    {
      id: "RF-007",
      name: "Area overlap not evaluated",
      outcome: "not_evaluated",
      summary: "No frozen approved area was supplied.",
    },
  ],
  access_code_source_hierarchy: [
    "selected_versioned_channel_definition",
    "approved_subscriber_programming_profile",
  ],
  squelch_rule:
    "CTCSS, DCS, NAC, or equivalent access-code differences never suppress RF-001 or RF-002.",
  disclaimer:
    "Decision support only. Results do not constitute frequency coordination, spectrum authorization, an interference determination, a propagation study, or operational approval. Qualified practitioners must review the results before operational use.",
};

const plan: ICS205Plan = {
  id: "plan-1",
  incident: incident.id,
  operational_period: "period-1",
  title: "Synthetic ICS-205",
  revisions: [
    {
      id: "revision-1",
      plan: "plan-1",
      number: 1,
      status: "approved",
      is_locked: true,
      prepared_by_name: "Synthetic COML",
      prepared_by_position: "COML",
      copied_from: null,
      approved_at: "2026-07-28T20:00:00Z",
      collaboration_version: 1,
      assignments: [],
      relationships: [],
    },
  ],
};

const channel: ConventionalChannel = {
  id: "resource-1",
  release: {
    id: "release-1",
    source: {
      id: "source-1",
      slug: "synthetic",
      name: "Synthetic Source",
      source_type: "synthetic",
      authoritative_url: "https://example.invalid/synthetic",
    },
    version: "synthetic-v1",
    released_on: "2026-07-28",
    effective_status: "effective",
    content_sha256: "a".repeat(64),
    document_title: "Synthetic fixture",
    publisher: "Synthetic publisher",
    retrieved_on: "2026-07-28",
    permitted_use: "Synthetic tests only.",
    transformation_method: "Synthetic construction",
    imported_at: "2026-07-28T19:00:00Z",
  },
  identifier: "SYN-OMITTED",
  name: "Synthetic active resource",
  channel_use: "Synthetic exercise",
  band: "VHF",
  jurisdiction: "Synthetic",
  rx_frequency_hz: 158_000_000,
  tx_frequency_hz: 158_000_000,
  bandwidth_hz: 12_500,
  mode: "analog_fm",
  rx_squelch: "",
  tx_squelch: "",
  emission_designator: "",
  eligibility: "",
  authorization: "",
  source_section: "",
  source_pages: "",
  restrictions: "",
  notes: "",
  is_active: true,
};

function analysis(
  overrides: Partial<DeconflictionAnalysis> = {},
): DeconflictionAnalysis {
  return {
    id: "analysis-1",
    incident: incident.id,
    approved_revision: "revision-1",
    revision_number: 1,
    rule_set_id: provisionalStatus.rule_set_id,
    rule_set_version: provisionalStatus.rule_set_version,
    status: "draft",
    input_snapshot: {
      schema_version: "rf-deconfliction-input-v2",
      approved_revision: {
        id: "revision-1",
        plan_id: "plan-1",
        number: 1,
        approved_at: "2026-07-28T20:00:00Z",
        approved_by_id: "1",
      },
      close_frequency_threshold_hz: 12_500,
      access_code_source_hierarchy:
        provisionalStatus.access_code_source_hierarchy,
      assignments: [{ id: "assignment-1" }, { id: "assignment-2" }],
    },
    input_sha256: "b".repeat(64),
    result_snapshot: {
      schema_version: "rf-deconfliction-result-v2",
      rule_set_id: provisionalStatus.rule_set_id,
      rule_set_version: provisionalStatus.rule_set_version,
      input_sha256: "b".repeat(64),
      rule_definitions: provisionalStatus.rules,
      analysis_status_definitions: provisionalStatus.analysis_statuses,
      warning_count: 1,
      warnings: [
        {
          finding_key: "d".repeat(64),
          rule_id: "RF-001",
          rule_name: "Co-channel overlap",
          rule_set_version: provisionalStatus.rule_set_version,
          severity: "critical",
          blocking: false,
          compared_inputs: [
            {
              id: "assignment-1",
              position: 1,
              function: "Command",
              name: "SYN CALL",
              assignment: "Synthetic command",
              operating_classification: "fixed_pair",
              technology_subtype: "",
              rx_frequency_hz: 155_000_000,
              tx_frequency_hz: 155_000_000,
              rx_squelch: "PL 100.0",
              tx_squelch: "PL 100.0",
              area_count: 1,
            },
            {
              id: "assignment-2",
              position: 2,
              function: "Operations",
              name: "SYN TAC",
              assignment: "Synthetic operations",
              operating_classification: "fixed_pair",
              technology_subtype: "",
              rx_frequency_hz: 155_000_000,
              tx_frequency_hz: 155_000_000,
              rx_squelch: "NAC 293",
              tx_squelch: "NAC 293",
              area_count: 1,
            },
          ],
          evidence: {
            separation_hz: 0,
            squelch_values_differ: true,
          },
          assumptions: [
            "Squelch values are evidence only and do not suppress warnings.",
          ],
          explanation:
            "SYN CALL and SYN TAC use the same operating frequency inside overlapping approved areas.",
          disclaimer: provisionalStatus.disclaimer,
        },
      ],
      analysis_status_count: 1,
      analysis_statuses: [
        {
          status_id: "RF-STATUS-002",
          status_name: "Subscriber access-code comparison not evaluated",
          outcome: "not_evaluated",
          rule_set_version: provisionalStatus.rule_set_version,
          assignment: {
            id: "assignment-1",
            position: 1,
            function: "Command",
            name: "SYN CALL",
            assignment: "Synthetic command",
            operating_classification: "fixed_pair",
            technology_subtype: "",
            rx_frequency_hz: 155_000_000,
            tx_frequency_hz: 155_000_000,
            rx_squelch: "PL 100.0",
            tx_squelch: "PL 100.0",
            area_count: 1,
          },
          affected_rule_ids: ["RF-008"],
          evidence: { unevaluated_directions: ["rx", "tx"] },
          explanation:
            "SYN CALL has no versioned comparison source, so RF-008 was not evaluated.",
          disclaimer: provisionalStatus.disclaimer,
        },
      ],
      disclaimer: provisionalStatus.disclaimer,
    },
    result_sha256: "c".repeat(64),
    warning_count: 1,
    created_by: 1,
    approved_by: null,
    approved_at: null,
    created_at: "2026-07-28T21:00:00Z",
    is_locked: false,
    finding_dispositions: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.getDeconflictionStatus.mockResolvedValue(provisionalStatus);
  api.listPlans.mockResolvedValue([plan]);
  api.listConventionalChannels.mockResolvedValue([channel]);
  api.listDeconflictionAnalyses.mockResolvedValue([analysis()]);
  api.createDeconflictionAnalysis.mockResolvedValue(
    analysis({ id: "analysis-2" }),
  );
  api.approveDeconflictionAnalysis.mockResolvedValue(
    analysis({ status: "approved", is_locked: true }),
  );
  api.createDeconflictionFindingDisposition.mockResolvedValue({
    id: "disposition-1",
    analysis: "analysis-1",
    finding_key: "d".repeat(64),
    rule_id: "RF-001",
    disposition: "reviewed_no_change",
    explanation: "Synthetic review.",
    created_by: 1,
    created_at: "2026-07-28T22:00:00Z",
  });
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

test("shows plain-language warnings, compared inputs, assumptions, and digests", async () => {
  const user = userEvent.setup();
  render(<DeconflictionWorkspace incident={incident} />);

  expect(
    await screen.findByText("rf-deconfliction-v2-reviewed", {
      selector: "strong",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      /equivalent access-code differences never suppress RF-001 or RF-002/i,
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", {
      level: 4,
      name: "RF-001: Co-channel overlap",
    }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/same operating frequency inside overlapping/i),
  ).toBeInTheDocument();

  const table = within(
    screen.getByRole("region", { name: "RF-001 compared inputs" }),
  ).getByRole("table");
  expect(within(table).getByText("SYN CALL")).toBeInTheDocument();
  expect(within(table).getByText(/PL 100.0/)).toBeInTheDocument();
  expect(within(table).getByText(/NAC 293/)).toBeInTheDocument();

  await user.click(screen.getByText("Evidence and assumptions"));
  expect(
    screen.getByText(/Squelch values are evidence only/i),
  ).toBeInTheDocument();
  await user.click(
    screen.getByText("Evidence digests and frozen input summary"),
  );
  expect(screen.getByText("b".repeat(64))).toBeInTheDocument();
  expect(screen.getByText("c".repeat(64))).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "Approve and lock analysis" }),
  ).not.toBeInTheDocument();
});

test("creates an analysis from an approved revision without an omission checklist", async () => {
  const user = userEvent.setup();
  render(<DeconflictionWorkspace incident={incident} />);

  await screen.findByText("rf-deconfliction-v2-reviewed", {
    selector: "strong",
  });
  await user.selectOptions(
    screen.getByLabelText("Approved ICS-205 revision"),
    "revision-1",
  );
  await user.click(
    screen.getByRole("button", { name: "Run deconfliction review" }),
  );

  expect(api.createDeconflictionAnalysis).toHaveBeenCalledWith({
    incident: incident.id,
    approved_revision: "revision-1",
  });
});

test("allows approval only after the exact rule set passes the practitioner gate", async () => {
  api.getDeconflictionStatus.mockResolvedValue({
    ...provisionalStatus,
    approved_for_operational_use: true,
  });
  const user = userEvent.setup();
  render(<DeconflictionWorkspace incident={incident} />);

  await screen.findByText("Qualified practitioner gate recorded");
  await user.click(
    screen.getByRole("button", { name: "Approve and lock analysis" }),
  );
  expect(api.approveDeconflictionAnalysis).toHaveBeenCalledWith("analysis-1");
});

test("records an append-only practitioner disposition for a retained finding", async () => {
  const user = userEvent.setup();
  render(<DeconflictionWorkspace incident={incident} />);

  await screen.findByRole("heading", {
    level: 4,
    name: "RF-001: Co-channel overlap",
  });
  await user.selectOptions(
    screen.getByLabelText("Disposition"),
    "special_accommodation_required",
  );
  await user.type(
    screen.getByLabelText("Explanation"),
    "Synthetic subscriber programming accommodation required.",
  );
  await user.click(
    screen.getByRole("button", { name: "Record append-only disposition" }),
  );

  expect(api.createDeconflictionFindingDisposition).toHaveBeenCalledWith(
    "analysis-1",
    {
      finding_key: "d".repeat(64),
      disposition: "special_accommodation_required",
      explanation: "Synthetic subscriber programming accommodation required.",
    },
  );
});

test("keeps retained v1 findings readable without applying v2 approval or disposition controls", async () => {
  const current = analysis();
  const legacy = analysis({
    rule_set_version: "rf-deconfliction-v1-provisional",
    result_snapshot: {
      ...current.result_snapshot,
      schema_version: "rf-deconfliction-result-v1",
      rule_set_version: "rf-deconfliction-v1-provisional",
      warnings: current.result_snapshot.warnings.map((warning) => ({
        ...warning,
        finding_key: undefined,
        blocking: undefined,
        compared_inputs: warning.compared_inputs.map((input) => ({
          ...input,
          position: undefined,
          function: undefined,
          assignment: undefined,
          operating_classification: undefined,
          technology_subtype: undefined,
          area_count: undefined,
        })),
      })),
      analysis_status_definitions: undefined,
      analysis_status_count: undefined,
      analysis_statuses: undefined,
    },
  });
  api.listDeconflictionAnalyses.mockResolvedValue([legacy]);

  render(<DeconflictionWorkspace incident={incident} />);

  expect(
    await screen.findByText(
      "This retained legacy result predates explicit not-applicable and not-evaluated statuses.",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      /This retained legacy finding predates deterministic finding keys/,
    ),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", {
      name: "Record append-only disposition",
    }),
  ).not.toBeInTheDocument();
});
