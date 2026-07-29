# Planning extension framework operations

## Scope

The governed extension framework keeps optional ICT planning tools and reports
separate from core incident and ICS-205 workflows. It supports only
application-shipped, code-reviewed registry entries. There is no arbitrary
upload, marketplace install, remote code, command, or dynamic module path.

The built-in `synthetic-readiness-summary` tool/report is non-operational test
evidence. It does not define a readiness requirement, approve a plan, or create
an official ICS form.

## Administrator workflow

1. Review the extension card's exact version, contract, source records,
   sensitivity, retention, approval, failure, accessibility, and export
   declarations.
2. Confirm the registry entry came from the reviewed application commit.
3. Select **Install disabled**. Installation snapshots the exact manifest and
   digest and does not make the extension runnable.
4. Complete any extension-specific human approval recorded in its issue.
5. Select **Enable compatible version** only when the installed version,
   contract, and manifest digest match the server registry.
6. Disable the extension before an upgrade or whenever its authority,
   compatibility, or acceptance evidence is uncertain.

Install, enable, and disable actions are audited. Hard deletion is not
supported. A changed registry manifest must be reinstalled while disabled and
reviewed again before enablement.

## User workflow

1. Select an incident and confirm the extension card says **enabled** and
   contract-compatible.
2. Select the declared tool or report capability.
3. Select an approved ICS-205 revision from the same incident.
4. Supply only the declared bounded inputs and run the extension.
5. Review the text classification, result state, source revision, versions,
   and evidence digests.
6. Download deterministic JSON when an inspectable package is needed.

The synthetic example reads assignment function and frequency-presence state
to produce counts; it does not include actual frequency values or protected
contact fields in its retained input/result or package.

## Authorization

| Action                              | Administrator | COML | COMC | COMT | Contributor | Read-only |
| ----------------------------------- | ------------- | ---- | ---- | ---- | ----------- | --------- |
| View authorized incident extensions | Yes           | Yes  | Yes  | Yes  | Yes         | Yes       |
| Run tool/report                     | Yes           | Yes  | Yes  | Yes  | No          | No        |
| Install, enable, or disable         | Yes           | No   | No   | No   | No          | No        |

Every list, detail, run, and export is scoped in the backend to active incident
membership. Global role permission alone does not grant access to another
incident.

## Compatibility and recovery

Contract `1.0` is the only supported initial version. The server rejects:

- an unknown extension or capability;
- an unsupported requested contract;
- an installed manifest whose version, contract, or digest differs from the
  current registry;
- a disabled or uninstalled extension;
- a draft or cross-incident source revision; and
- undeclared, oversized, or out-of-range input.

Do not bypass incompatibility by editing the database. Disable the extension,
confirm the reviewed application commit and migration state, reinstall its
registered manifest, rerun synthetic evidence, and enable it only after the
applicable human gate.

An optional run failure returns bounded recovery text and a retained failed
execution. Core incident and plan routes remain available. Preserve the failed
record and audit event; do not edit them in place. Correct the code or
configuration through a reviewed change and run again, creating new evidence.

## Retention, backup, and restore

Installation records, execution input/result snapshots, digests, failures, and
export audit events are part of the application database. They follow incident
retention and legal-hold requirements and are not automatically purged.

The standard PostgreSQL backup and isolated restore drill includes the
`extensions_extensioninstallation` and `extensions_extensionexecution` tables.
After a restore, verify:

1. migration `extensions.0001_initial` is applied;
2. installed extensions remain in the expected disabled/enabled state;
3. retained execution input and result digests recompute correctly;
4. incident authorization still hides cross-incident records; and
5. one synthetic completed execution exports byte-identical JSON on repeated
   download.

Restore does not re-authorize or upgrade an extension. If application code and
the restored manifest differ, the registry reports incompatibility and the
extension cannot run until an Administrator reviews and reinstalls it disabled.

## Proposal gate for a future extension

Open a dedicated issue before implementation and record:

- operational objective, qualified owner, and governing authority;
- exact users, incident/revision scope, permissions, and approval behavior;
- source records and provenance, data classification, sensitive fields,
  retention/legal hold, and permitted exports;
- versioned input/output schemas, validation, determinism, and failure
  behavior;
- accessibility alternatives and manual evaluation plan;
- tested limits, concurrency/job/cancellation/recovery design, backup/restore,
  and audit evidence;
- whether output is draft, decision support, or official; and
- qualified practitioner, security/privacy, records, and maintainer approval.

Issue #24 does not authorize unspecified operational forms or workflows.
