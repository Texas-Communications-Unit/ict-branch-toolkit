import type {
  CalibrationSet,
  CalibrationStatus,
  CoverageEngineStatus,
  CoverageEstimate,
  CreateDirectionalCoverageAnalysisPayload,
  ConventionalChannel,
  CoordinateParseResult,
  CreateHAATCalculationPayload,
  CreateCoverageEstimatePayload,
  CreateCalibrationSetPayload,
  CreateSubscriberProfilePayload,
  CreateFieldObservationPayload,
  CreateDeconflictionAnalysisPayload,
  DeconflictionAnalysis,
  DeconflictionRuleSetStatus,
  DirectionalAnalysisStatus,
  DirectionalCoverageAnalysis,
  CurrentUser,
  EditableRFInputFields,
  ElevationProviderStatus,
  FieldObservation,
  GeocoderSearchResult,
  HAATCalculation,
  ImportResult,
  Incident,
  ICS205Plan,
  Paginated,
  PlanAssignment,
  PlanRelationship,
  PlanRevision,
  Phase2ExportVerification,
  Phase2ValidationBundle,
  Phase2ValidationStatus,
  CreatePhase2ValidationBundlePayload,
  RFAnalysisInputSnapshot,
  RevisionComparison,
  RadioSite,
  SiteAssignment,
  SubscriberProfile,
  SubscriberProfileVersion,
  TrunkedTalkgroup,
  UpdateSubscriberProfilePayload,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_KEY = "ict-toolkit-token";
const TOKEN_EXPIRES_AT_KEY = "ict-toolkit-token-expires-at";
export const AUTHENTICATION_EXPIRED_EVENT =
  "ict-toolkit-authentication-expired";

export function clearSession(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(TOKEN_EXPIRES_AT_KEY);
}

function storedToken(): string | null {
  const token = sessionStorage.getItem(TOKEN_KEY);
  const expiresAt = sessionStorage.getItem(TOKEN_EXPIRES_AT_KEY);
  if (!token) {
    clearSession();
    return null;
  }
  if (
    !expiresAt ||
    !Number.isFinite(Date.parse(expiresAt)) ||
    Date.now() >= Date.parse(expiresAt)
  ) {
    expireSession();
    return null;
  }
  return token;
}

export function hasActiveSession(): boolean {
  return storedToken() !== null;
}

function expireSession(): void {
  clearSession();
  window.dispatchEvent(new Event(AUTHENTICATION_EXPIRED_EVENT));
}

function tokenForRequest(): string | null {
  const hadStoredToken = sessionStorage.getItem(TOKEN_KEY) !== null;
  const token = storedToken();
  if (hadStoredToken && !token) {
    throw new Error("Your session expired. Sign in again.");
  }
  return token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = tokenForRequest();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    if (response.status === 401 && token) {
      expireSession();
      throw new Error("Your session expired. Sign in again.");
    }
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function login(username: string, password: string): Promise<void> {
  const response = await fetch(`${API_BASE}/api/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    clearSession();
    throw new Error((await response.text()) || "Sign-in failed.");
  }
  const result = (await response.json()) as {
    token: string;
    expires_at: string;
  };
  if (
    !result.token ||
    !result.expires_at ||
    !Number.isFinite(Date.parse(result.expires_at))
  ) {
    clearSession();
    throw new Error("The sign-in response was invalid.");
  }
  sessionStorage.setItem(TOKEN_KEY, result.token);
  sessionStorage.setItem(TOKEN_EXPIRES_AT_KEY, result.expires_at);
}

export async function logout(): Promise<boolean> {
  let serverRevocationConfirmed = true;
  try {
    if (storedToken()) {
      await request<void>("/api/auth/logout/", { method: "POST" });
    }
  } catch {
    serverRevocationConfirmed = false;
  } finally {
    clearSession();
  }
  return serverRevocationConfirmed;
}

export async function listIncidents(): Promise<Incident[]> {
  const result = await request<Paginated<Incident>>("/api/incidents/");
  return result.results;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return request<CurrentUser>("/api/me/");
}

export async function listConventionalChannels(): Promise<
  ConventionalChannel[]
> {
  const result = await request<Paginated<ConventionalChannel>>(
    "/api/conventional-channels/",
  );
  return result.results;
}

export async function listTrunkedTalkgroups(): Promise<TrunkedTalkgroup[]> {
  const result = await request<Paginated<TrunkedTalkgroup>>(
    "/api/trunked-talkgroups/",
  );
  return result.results;
}

export function importChannelLibrary(payload: object): Promise<ImportResult> {
  return request<ImportResult>("/api/channel-imports/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function createIncident(
  name: string,
  incidentNumber: string,
): Promise<Incident> {
  return request<Incident>("/api/incidents/", {
    method: "POST",
    body: JSON.stringify({ name, incident_number: incidentNumber }),
  });
}

export async function createOperationalPeriod(
  incident: string,
  name: string,
  startsAt: string,
  endsAt: string,
): Promise<void> {
  await request("/api/operational-periods/", {
    method: "POST",
    body: JSON.stringify({
      incident,
      name,
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
    }),
  });
}

export async function archiveIncident(incident: string): Promise<void> {
  await request(`/api/incidents/${incident}/archive/`, { method: "POST" });
}

export async function listPlans(): Promise<ICS205Plan[]> {
  const result = await request<Paginated<ICS205Plan>>("/api/ics205-plans/");
  return result.results;
}

export function createPlan(
  incident: string,
  operationalPeriod: string,
): Promise<ICS205Plan> {
  return request<ICS205Plan>("/api/ics205-plans/", {
    method: "POST",
    body: JSON.stringify({
      incident,
      operational_period: operationalPeriod,
      title: "Incident Radio Communications Plan",
    }),
  });
}

export function createPlanAssignment(
  payload: Record<string, unknown>,
): Promise<PlanAssignment> {
  return request<PlanAssignment>("/api/plan-assignments/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deletePlanAssignment(id: string): Promise<void> {
  return request<void>(`/api/plan-assignments/${id}/`, { method: "DELETE" });
}

export function reorderPlanAssignments(
  revision: string,
  assignmentIds: string[],
): Promise<PlanAssignment[]> {
  return request<PlanAssignment[]>("/api/plan-assignments/reorder/", {
    method: "POST",
    body: JSON.stringify({ revision, assignment_ids: assignmentIds }),
  });
}

export function createPlanRelationship(
  payload: Record<string, unknown>,
): Promise<PlanRelationship> {
  return request<PlanRelationship>("/api/plan-relationships/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approvePlanRevision(id: string): Promise<PlanRevision> {
  return request<PlanRevision>(`/api/plan-revisions/${id}/approve/`, {
    method: "POST",
  });
}

export function copyPlanRevision(id: string): Promise<PlanRevision> {
  return request<PlanRevision>(`/api/plan-revisions/${id}/copy/`, {
    method: "POST",
  });
}

export function comparePlanRevisions(
  id: string,
  other: string,
): Promise<RevisionComparison> {
  return request<RevisionComparison>(
    `/api/plan-revisions/${id}/compare/?other=${encodeURIComponent(other)}`,
  );
}

export async function downloadPlanPdf(id: string): Promise<void> {
  const token = tokenForRequest();
  const response = await fetch(`${API_BASE}/api/plan-revisions/${id}/pdf/`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  });
  if (!response.ok) throw new Error(await response.text());
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "ics-205.pdf";
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function listRadioSites(incident: string): Promise<RadioSite[]> {
  const result = await request<Paginated<RadioSite>>(
    `/api/radio-sites/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function parseCoordinate(
  coordinate: string,
): Promise<CoordinateParseResult> {
  return request<CoordinateParseResult>("/api/coordinates/parse/", {
    method: "POST",
    body: JSON.stringify({ coordinate }),
  });
}

export function createRadioSite(
  payload: Record<string, unknown>,
): Promise<RadioSite> {
  return request<RadioSite>("/api/radio-sites/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRadioSite(
  id: string,
  payload: Record<string, unknown>,
): Promise<RadioSite> {
  return request<RadioSite>(`/api/radio-sites/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function createManualRing(
  payload: Record<string, unknown>,
): Promise<void> {
  return request("/api/manual-rings/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function listSiteAssignments(
  revision: string,
): Promise<SiteAssignment[]> {
  const result = await request<Paginated<SiteAssignment>>(
    `/api/site-assignments/?revision=${encodeURIComponent(revision)}`,
  );
  return result.results;
}

export function createSiteAssignment(
  site: string,
  assignment: string,
): Promise<SiteAssignment> {
  return request<SiteAssignment>("/api/site-assignments/", {
    method: "POST",
    body: JSON.stringify({ site, assignment }),
  });
}

export function searchAddress(address: string): Promise<GeocoderSearchResult> {
  return request<GeocoderSearchResult>("/api/geocoder/search/", {
    method: "POST",
    body: JSON.stringify({ address }),
  });
}

export async function downloadSpatialExport(
  revision: string,
  format: "map" | "kml" | "geojson" | "csv",
): Promise<void> {
  const token = tokenForRequest();
  const response = await fetch(
    `${API_BASE}/api/spatial-exports/${revision}/${format}/`,
    { headers: token ? { Authorization: `Token ${token}` } : {} },
  );
  if (!response.ok) throw new Error(await response.text());
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download =
    format === "map" ? "approved-site-map.svg" : `approved-sites.${format}`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export async function listSubscriberProfiles(
  incident: string,
): Promise<SubscriberProfile[]> {
  const result = await request<Paginated<SubscriberProfile>>(
    `/api/subscriber-profiles/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createSubscriberProfile(
  payload: CreateSubscriberProfilePayload,
): Promise<SubscriberProfile> {
  return request<SubscriberProfile>("/api/subscriber-profiles/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateSubscriberProfile(
  id: string,
  payload: UpdateSubscriberProfilePayload,
): Promise<SubscriberProfile> {
  return request<SubscriberProfile>(`/api/subscriber-profiles/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function archiveSubscriberProfile(id: string): Promise<void> {
  return request<void>(`/api/subscriber-profiles/${id}/archive/`, {
    method: "POST",
  });
}

export async function listSubscriberProfileVersions(
  profile: string,
): Promise<SubscriberProfileVersion[]> {
  const result = await request<Paginated<SubscriberProfileVersion>>(
    `/api/subscriber-profile-versions/?profile=${encodeURIComponent(profile)}`,
  );
  return result.results;
}

export function updateSubscriberProfileVersion(
  id: string,
  payload: EditableRFInputFields,
): Promise<SubscriberProfileVersion> {
  return request<SubscriberProfileVersion>(
    `/api/subscriber-profile-versions/${id}/`,
    {
      method: "PATCH",
      body: JSON.stringify(payload),
    },
  );
}

export function copySubscriberProfileVersion(
  id: string,
): Promise<SubscriberProfileVersion> {
  return request<SubscriberProfileVersion>(
    `/api/subscriber-profile-versions/${id}/copy/`,
    { method: "POST" },
  );
}

export function approveSubscriberProfileVersion(
  id: string,
): Promise<SubscriberProfileVersion> {
  return request<SubscriberProfileVersion>(
    `/api/subscriber-profile-versions/${id}/approve/`,
    { method: "POST" },
  );
}

export function createRFAnalysisInputSnapshot(
  id: string,
  label: string,
): Promise<RFAnalysisInputSnapshot> {
  return request<RFAnalysisInputSnapshot>(
    `/api/subscriber-profile-versions/${id}/create_snapshot/`,
    {
      method: "POST",
      body: JSON.stringify({ label }),
    },
  );
}

export async function listRFAnalysisInputSnapshots(
  incident: string,
): Promise<RFAnalysisInputSnapshot[]> {
  const result = await request<Paginated<RFAnalysisInputSnapshot>>(
    `/api/rf-analysis-input-snapshots/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function getElevationProviderStatus(): Promise<ElevationProviderStatus> {
  return request<ElevationProviderStatus>("/api/elevation-provider/");
}

export async function listHAATCalculations(
  incident: string,
): Promise<HAATCalculation[]> {
  const result = await request<Paginated<HAATCalculation>>(
    `/api/haat-calculations/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createHAATCalculation(
  payload: CreateHAATCalculationPayload,
): Promise<HAATCalculation> {
  return request<HAATCalculation>("/api/haat-calculations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function retryHAATCalculation(id: string): Promise<HAATCalculation> {
  return request<HAATCalculation>(`/api/haat-calculations/${id}/retry/`, {
    method: "POST",
  });
}

export function approveHAATCalculation(id: string): Promise<HAATCalculation> {
  return request<HAATCalculation>(`/api/haat-calculations/${id}/approve/`, {
    method: "POST",
  });
}

export function getCoverageEngineStatus(): Promise<CoverageEngineStatus> {
  return request<CoverageEngineStatus>("/api/coverage-engine/");
}

export async function listCoverageEstimates(
  incident: string,
): Promise<CoverageEstimate[]> {
  const result = await request<Paginated<CoverageEstimate>>(
    `/api/coverage-estimates/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createCoverageEstimate(
  payload: CreateCoverageEstimatePayload,
): Promise<CoverageEstimate> {
  return request<CoverageEstimate>("/api/coverage-estimates/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveCoverageEstimate(id: string): Promise<CoverageEstimate> {
  return request<CoverageEstimate>(`/api/coverage-estimates/${id}/approve/`, {
    method: "POST",
  });
}

export function getDirectionalAnalysisStatus(): Promise<DirectionalAnalysisStatus> {
  return request<DirectionalAnalysisStatus>(
    "/api/directional-analysis-status/",
  );
}

export async function listDirectionalCoverageAnalyses(
  incident: string,
): Promise<DirectionalCoverageAnalysis[]> {
  const result = await request<Paginated<DirectionalCoverageAnalysis>>(
    `/api/directional-coverage-analyses/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createDirectionalCoverageAnalysis(
  payload: CreateDirectionalCoverageAnalysisPayload,
): Promise<DirectionalCoverageAnalysis> {
  return request<DirectionalCoverageAnalysis>(
    "/api/directional-coverage-analyses/",
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function approveDirectionalCoverageAnalysis(
  id: string,
): Promise<DirectionalCoverageAnalysis> {
  return request<DirectionalCoverageAnalysis>(
    `/api/directional-coverage-analyses/${id}/approve/`,
    { method: "POST" },
  );
}

export function getCalibrationStatus(): Promise<CalibrationStatus> {
  return request<CalibrationStatus>("/api/calibration-status/");
}

export async function listFieldObservations(
  incident: string,
): Promise<FieldObservation[]> {
  const result = await request<Paginated<FieldObservation>>(
    `/api/field-observations/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createFieldObservation(
  payload: CreateFieldObservationPayload,
): Promise<FieldObservation> {
  return request<FieldObservation>("/api/field-observations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function reviewFieldObservation(
  id: string,
  decision: "approved" | "excluded",
  reason: string,
): Promise<FieldObservation> {
  return request<FieldObservation>(`/api/field-observations/${id}/review/`, {
    method: "POST",
    body: JSON.stringify({ decision, reason }),
  });
}

export async function listCalibrationSets(
  incident: string,
): Promise<CalibrationSet[]> {
  const result = await request<Paginated<CalibrationSet>>(
    `/api/calibration-sets/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createCalibrationSet(
  payload: CreateCalibrationSetPayload,
): Promise<CalibrationSet> {
  return request<CalibrationSet>("/api/calibration-sets/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveCalibrationSet(id: string): Promise<CalibrationSet> {
  return request<CalibrationSet>(`/api/calibration-sets/${id}/approve/`, {
    method: "POST",
  });
}

export function getDeconflictionStatus(): Promise<DeconflictionRuleSetStatus> {
  return request<DeconflictionRuleSetStatus>("/api/deconfliction-status/");
}

export async function listDeconflictionAnalyses(
  incident: string,
): Promise<DeconflictionAnalysis[]> {
  const result = await request<Paginated<DeconflictionAnalysis>>(
    `/api/deconfliction-analyses/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createDeconflictionAnalysis(
  payload: CreateDeconflictionAnalysisPayload,
): Promise<DeconflictionAnalysis> {
  return request<DeconflictionAnalysis>("/api/deconfliction-analyses/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function approveDeconflictionAnalysis(
  id: string,
): Promise<DeconflictionAnalysis> {
  return request<DeconflictionAnalysis>(
    `/api/deconfliction-analyses/${id}/approve/`,
    { method: "POST" },
  );
}

export function getPhase2ValidationStatus(): Promise<Phase2ValidationStatus> {
  return request<Phase2ValidationStatus>("/api/phase2-validation-status/");
}

export async function listPhase2ValidationBundles(
  incident: string,
): Promise<Phase2ValidationBundle[]> {
  const result = await request<Paginated<Phase2ValidationBundle>>(
    `/api/phase2-validation-bundles/?incident=${encodeURIComponent(incident)}`,
  );
  return result.results;
}

export function createPhase2ValidationBundle(
  payload: CreatePhase2ValidationBundlePayload,
): Promise<Phase2ValidationBundle> {
  return request<Phase2ValidationBundle>("/api/phase2-validation-bundles/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runPhase2ValidationBundle(
  id: string,
): Promise<Phase2ValidationBundle> {
  return request<Phase2ValidationBundle>(
    `/api/phase2-validation-bundles/${id}/run/`,
    { method: "POST" },
  );
}

export function cancelPhase2ValidationBundle(
  id: string,
): Promise<Phase2ValidationBundle> {
  return request<Phase2ValidationBundle>(
    `/api/phase2-validation-bundles/${id}/cancel/`,
    { method: "POST" },
  );
}

export function retryPhase2ValidationBundle(
  id: string,
): Promise<Phase2ValidationBundle> {
  return request<Phase2ValidationBundle>(
    `/api/phase2-validation-bundles/${id}/retry/`,
    { method: "POST" },
  );
}

export function approvePhase2ValidationBundle(
  id: string,
): Promise<Phase2ValidationBundle> {
  return request<Phase2ValidationBundle>(
    `/api/phase2-validation-bundles/${id}/approve/`,
    { method: "POST" },
  );
}

export async function downloadPhase2ValidationBundle(
  id: string,
): Promise<void> {
  const token = tokenForRequest();
  const response = await fetch(
    `${API_BASE}/api/phase2-validation-bundles/${id}/export/`,
    { headers: token ? { Authorization: `Token ${token}` } : {} },
  );
  if (!response.ok) throw new Error(await response.text());
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `phase-2-validation-${id}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function verifyPhase2ValidationExport(
  id: string,
  contentSha256: string,
): Promise<Phase2ExportVerification> {
  return request<Phase2ExportVerification>(
    `/api/phase2-validation-bundles/${id}/verify/`,
    {
      method: "POST",
      body: JSON.stringify({ content_sha256: contentSha256 }),
    },
  );
}
