# ADR-0018: Controlled offline and intermittent-connectivity operation

- Status: Accepted for synthetic evaluation
- Date: 2026-07-28
- Decision owners: Maintainers, security/privacy, records management, and operations reviewers

## Context

Incident planners may temporarily lose the application network while they still need bounded access
to an incident plan. A general-purpose browser cache, a complete database copy, or last-writer-wins
synchronization would expose unnecessary data and could silently overwrite approved or concurrent
records. Browser storage also creates theft, shared-device, retention, support, and revocation risks.

The application therefore needs a narrow continuity mechanism whose data selection, local
protection, mutation order, conflict behavior, expiration, and retained evidence are explicit.

## Decision

Offline packaging is disabled by default. `ICT_OFFLINE_ENABLED=true` enables only this versioned
contract; `ICT_OFFLINE_APPROVED_FOR_NON_SYNTHETIC_USE` remains a separate human-gate record and
defaults to `false`.

An authorized user creates an incident-scoped package by explicitly selecting:

- one to five plan revisions;
- zero or more reference-library releases;
- zero or more incident sites and an optional vector-only map descriptor;
- zero or more retained terrain analyses.

Attachments are unavailable until a controlled attachment subsystem exists. Network map tiles,
authentication tokens, credentials, provider keys, and unselected incident records are never placed
in the package. Server limits bound package bytes, queue length, expiration, and clock skew.

The browser stores the package and queued mutations as one AES-256-GCM encrypted IndexedDB
envelope. A per-package random salt and PBKDF2-SHA-256 with 310,000 iterations derive the key from
the device-only passphrase. The passphrase and derived key are never persisted by the application.
The envelope binds the package ID and manifest digest as authenticated additional data. Encryption
protects locked data at rest; it cannot protect an unlocked session, a compromised browser, a
keylogger, or a user who discloses the passphrase.

The service worker caches the application shell and same-origin static assets. It excludes every
`/api/` request and does not cache external map tiles. Runtime-cache clearing and encrypted-package
purge are separate operations.

Offline changes are limited to:

- editing prepared-by fields on a packaged draft revision;
- creating, editing, or deleting assignments on a packaged draft revision.

Each local mutation has a stable client-generated UUID, actor and device context, sequence,
previous hash, canonical payload digest, and mutation digest. The server verifies the chain,
package identity, current authorization, clock, exact scope, queue bounds, object timestamp, and a
server-side revision digest. Receipts are append-only and duplicate submissions are idempotent.

Approved revisions are always read-only. A changed revision, changed object, missing object,
revoked membership, broken chain, unsupported operation, or earlier unresolved conflict never uses
last-writer-wins behavior. The operator must explicitly discard the local change or record a
refresh-and-requeue decision. Refresh-and-requeue does not apply content automatically.

Lock removes the browser's usable key material and optionally locks the server package. Expiration
blocks unlock and synchronization and purges expired local ciphertext during capability refresh.
Controlled purge clears server payload and revision state plus local ciphertext while retaining the
manifest digest, mutation receipts, conflict decisions, and audit evidence.

Audit events retain identifiers, counts, sequence, versions, and digests. Support bundles exclude
tokens, keys, passphrases, ciphertext, incident payloads, mutation payloads, frequencies,
coordinates, names, and notes.

## Consequences

- Core online operation remains available when offline packaging is disabled or absent.
- The first implementation supports bounded plan drafting, not full application operation.
- Users must retain their own passphrase; administrators cannot recover it.
- Multiple devices can produce conflicts that require deliberate review.
- Local browser encryption reduces theft-at-rest exposure but does not make a general-purpose
  browser a hardened classified-data device.
- Non-synthetic use remains prohibited until the issue's security, privacy, records-management,
  operations, and maintainer gate approves the exact scope and deployment controls.

## Alternatives considered

- **Cache all API responses:** rejected because scope, expiration, revocation, and data sensitivity
  would be implicit.
- **Store plaintext IndexedDB records:** rejected because a locked browser profile or copied device
  storage could expose incident content.
- **Persist an encryption key beside the ciphertext:** rejected because it would provide little
  meaningful protection at rest.
- **Last writer wins:** rejected because it can silently rewrite operational records.
- **Allow offline approval and official exports:** rejected because those actions require current
  authorization and current server state.
- **Cache third-party map tiles:** rejected pending provider terms, attribution, retention, and
  redistribution approval.
