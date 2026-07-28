# Offline and intermittent-connectivity operation

> **PROVISIONAL AND SYNTHETIC-ONLY:** Offline packaging is disabled by default. Enabling the
> feature does not approve non-synthetic incident data, a device, a browser, a retention schedule,
> or an operating procedure.

## Human gate

Before any non-synthetic use, named security, privacy, records-management, operational, and
maintainer reviewers must approve and record:

1. the exact offline-capable operations and prohibited actions;
2. incident classifications permitted on each managed device class;
3. device encryption, screen lock, patching, browser profile, malware protection, physical
   custody, remote-wipe, and shared-device rules;
4. package expiration, legal hold, retention, disclosure, backup, and destruction rules;
5. passphrase creation, custody, loss, compromise, and recovery expectations;
6. package, queue, clock-skew, concurrency, and storage limits;
7. service-worker update and emergency cache-clearing procedures;
8. conflict authority and the required operational review before requeue;
9. support-bundle handling and approved support recipients;
10. synthetic positive, negative, boundary, revocation, recovery, and rollback evidence.

Leave `ICT_OFFLINE_APPROVED_FOR_NON_SYNTHETIC_USE=false` until that record exists. This setting is a
deployment assertion, not an application-side approval workflow.

## Capability boundary

The status card and `GET /api/offline-status/` are authoritative for configured limits.

Supported operations are draft prepared-by updates and draft assignment create/update/delete.
Approved revisions, plan approval, official exports, access changes, reference imports, attachments,
provider refreshes, and terrain/RF/network operations are unavailable offline.

A package contains only explicitly selected revisions, resource releases, sites, vector-map
metadata, and terrain analyses. It never contains a token, credential, provider key, network map
tile, or an implicit "whole incident" copy.

## Synthetic evaluation configuration

Use a protected environment file outside the repository:

```dotenv
ICT_OFFLINE_ENABLED=true
ICT_OFFLINE_APPROVED_FOR_NON_SYNTHETIC_USE=false
ICT_OFFLINE_MAX_PACKAGE_BYTES=5242880
ICT_OFFLINE_MAX_QUEUE_ITEMS=500
ICT_OFFLINE_DEFAULT_TTL_HOURS=24
ICT_OFFLINE_MAX_TTL_HOURS=72
ICT_OFFLINE_CLOCK_SKEW_SECONDS=300
```

Changing a limit requires security and operational review plus deterministic boundary evidence.
Package size is measured over canonical server JSON before it reaches the browser.

## Operator workflow

1. While connected, select one incident and every revision, release, site, map descriptor, and
   terrain result needed offline. Do not select data merely because it might be useful.
2. Confirm the expiration and create a unique device-only passphrase of at least 12 characters.
   The Toolkit does not store or recover the passphrase.
3. Verify the package ID, manifest digest, expiration, classification, and selected counts.
4. Lock the package whenever the device is unattended. Locking removes usable key material from
   the browser session.
5. During network loss, review the visible unsupported-action list. Add only bounded draft changes
   to the encrypted ordered queue.
6. On reconnect, correct any device-clock warning, confirm current access, review every pending
   item in sequence, and start synchronization explicitly. Reconnect never auto-submits changes.
7. Review the result of every item. Applied and exact duplicate items leave the pending queue.
   Conflict and rejection items remain visible.
8. For a conflict, compare the current server record with the local intent. Choose either:
   - **Keep server record:** discard the local content; or
   - **Refresh and requeue:** record the decision, refresh current data, and create a new mutation.
9. Lock or purge the package when continuity work ends. Purge is required at expiration unless a
   documented legal hold changes the normal rule.

Never approve a plan, publish an official export, or make an access decision from an offline copy.

## Revocation, expiration, and storage limits

- Current membership and edit permission are checked at synchronization. Revocation marks the
  server package revoked; no queued content is applied.
- Local lock always removes the in-memory passphrase and unlocked package, even if the server lock
  request fails. The operator must complete the server lock or purge after reconnect.
- An expired server package cannot synchronize or unlock. Expired local ciphertext is purged when
  the browser refreshes offline capability.
- Local purge removes device ciphertext even when the server is unavailable. It reports whether
  the separate server purge still needs to be completed.
- A browser quota failure leaves the package unsaved locally, reports the limit, and attempts to
  lock the newly created server package. If that lock also fails, reconnect and lock or purge the
  server package before continuing. Reduce the explicit scope or purge an older local package.
- Do not raise size, queue, or expiration limits to bypass a failed test or device constraint.

## App updates and safe cache clearing

The service worker caches only the root app shell, its built `/assets/`, the manifest, and
same-origin `/brand/` files. API responses, arbitrary same-origin paths, and external map tiles are
excluded. The installation step resolves and caches the root document's built JavaScript and CSS
assets so an offline browser restart does not depend on the network.

- **Check for app update** asks the browser to fetch the current worker.
- **Activate downloaded update** activates a waiting worker; finish or record pending work first.
- **Clear runtime caches** removes only runtime app-shell assets.
- **Purge local package** separately removes encrypted incident ciphertext.

Do not tell a user that clearing the app cache removed incident data, and do not use package purge
as a substitute for a normal browser update.

## Support and recovery

The support export combines minimized server and local metadata. It excludes authentication tokens,
keys, passphrases, ciphertext, package content, mutation content, frequencies, coordinates, names,
and notes. Treat even minimized IDs and timing as incident-associated metadata.

If the passphrase is lost, the local package is unrecoverable by design. Purge it, reconnect, verify
current access, and create a new explicitly scoped package. Never add a recovery key beside the
ciphertext.

If synchronization fails:

1. leave the package locked when not actively troubleshooting;
2. export the minimized support bundle;
3. record package ID, manifest digest, time, client/server versions, network state, and the visible
   error without copying incident content into a ticket;
4. verify the audit chain and current membership;
5. do not edit receipts, database state, sequence, or hashes to force progress.

## Verification checklist

Use synthetic fixtures to verify package allowlisting, approved-revision lockout, AES-GCM
round-trip and wrong-passphrase failure, app install/update, network loss and reconnect, quota
failure, ordered queue and cancellation, broken/reordered chain rejection, duplicate idempotency,
clock skew, stale base, partial synchronization, revocation, both conflict decisions, expiration,
lock/unlock, package purge, safe runtime-cache clearing, minimized support export, append-only
receipts, migration drift, PostgreSQL/PostGIS behavior, accessibility, and rollback.

See [ADR-0018](../adr/0018-controlled-offline-and-intermittent-operation.md), the
[threat model](../security/threat-model.md), and the
[data-classification standard](../security/data-classification.md).
