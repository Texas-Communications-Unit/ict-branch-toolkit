# Prototype Threat Assumptions

## Assets

Future assets include approved communications plans, source/version provenance, user authority, audit history, site coordinates, exports, and configuration. P1.0 permits synthetic data only.

## Primary threats

- Unauthorized reading or alteration of drafts and approved information.
- A UI-only control being bypassed through direct API access.
- Secrets or operational data entering source control, logs, fixtures, or screenshots.
- Published information losing its source, approval, or revision linkage.
- Malicious imports, file uploads, map styles, or external integrations.
- Dependency or container compromise.
- Planning warnings being interpreted as technical or legal authorization.

## Design responses

Enforce policy in the backend, keep approved revisions immutable, retain provenance, use append-only audit design, validate imports before persistence, isolate external integrations, scan dependencies/secrets/containers, and label limitations at user and export boundaries. Later milestones must add formal abuse cases and security tests as those surfaces are implemented.

