# Online collaboration operations

## Scope

P3.3 provides an online-only collaboration foundation for the ICS-205. It does
not support offline editing, background synchronization, or an offline change
queue. Users must have a current authenticated server connection to save.

## Operator workflow

1. Open the incident and current draft ICS-205.
2. Confirm that **Online collaboration active** appears. The user list is an
   advisory presence indicator, not a lock.
3. Work normally. Assignment creation, deletion, and reorder include the version
   the browser loaded.
4. If another user changes the same record first, the Toolkit retains the
   proposed values and shows them beside the current saved values. Nothing is
   silently overwritten.
5. Choose one action:
   - **Keep currently saved values** records a discard resolution; or
   - **Apply my proposed values** submits a new version-checked change and, if it
     succeeds, records an intentional replacement.
6. If the record changes again during review, compare the new current values and
   decide again.
7. Copy an approved revision to a new draft before attempting changes.

The browser polls plan state, presence, and recent change evidence every 20
seconds. Manual refresh remains safe. A disconnected browser cannot save; when
the connection returns it reloads current server state and normal version checks
apply.

## Permission administration

Global and incident roles remain Administrator, COML, COMC, COMT, Contributor,
and Read-only. Existing backend policy controls plan view, edit, approval, and
export. Incident membership is checked on every collaboration request.

The following contact fields receive additional field policy:

- `contact_name`
- `site_address`
- `phone_numbers`
- `contact_24_hour`

The provisional default preserves the existing tested policy: Administrator,
COML, and COMC may view or edit those fields. COMT, Contributor, Read-only, and
new roles fail closed. An Administrator can create a per-incident
sensitive-field rule through the API or protected Django administration path.
Each rule specifies independent view and edit role arrays and whether an
unauthorized response omits the field or returns `[REDACTED]`. Rules are
retained, versioned, validated, and audited; they cannot be deleted through the
API.

Do not broaden the default role arrays in shared deployment configuration until
the Issue #23 security/privacy and incident-practitioner human gate approves the
matrix. A blank value, omitted field, and `[REDACTED]` value have different
meanings.

## Presence privacy and recovery

The default presence lease is 75 seconds and may be configured between 30 and
300 seconds. Clients should heartbeat more frequently than the lease. Abrupt
browser or workstation loss needs no manual unlock; the lease expires.

Permission revocation takes effect on the user's next API request. A revoked
user cannot renew or list presence or submit another mutation. Short-lived
presence already visible to other authorized incident users expires normally.

Presence is deliberately minimal. Do not add field values, contact details,
locations, tokens, browser history, typing state, or detailed activity
telemetry.

## Conflict and audit recovery

`CollaborationChange` retains saved, conflict, and rejected outcomes. The record
contains protected proposed/current snapshots in the application database;
responses are filtered through the current field policy. General audit events
contain only identifiers, field names, versions, dispositions, and SHA-256
digests.

Database administrators must protect collaboration tables as incident data.
Normal backup, restore, retention, and access logging procedures apply. Model
guards are not protection against a privileged database administrator.

If a user reports a missing change:

1. identify the incident, revision, approximate time, actor, and client mutation
   UUID if available;
2. inspect the retained collaboration change and append-only audit event;
3. confirm whether the disposition was saved, conflict, or rejected;
4. never edit the retained record in place; and
5. recover an intended value through a new authorized mutation or a new draft
   revision.

## Configuration

```dotenv
ICT_COLLABORATION_PRESENCE_TTL_SECONDS=75
ICT_COLLABORATION_HISTORY_LIMIT=100
ICT_RESTRICTED_FIELD_DEFAULT_VIEW_ROLES=["administrator","coml","comc"]
ICT_RESTRICTED_FIELD_DEFAULT_EDIT_ROLES=["administrator","coml","comc"]
```

History responses are bounded between 10 and 500 records. The setting controls
one response, not database retention.

The external identity status is intentionally disabled:

```dotenv
ICT_EXTERNAL_SSO_ENABLED=false
ICT_EXTERNAL_IDENTITY_PROVIDER=apps.accounts.external_identity.DisabledExternalIdentityProvider
ICT_EXTERNAL_ROLE_MAPPINGS={}
```

Do not set live credentials or connection details in source control. A future
provider requires a separate reviewed implementation; these settings do not
activate WordPress/CiviCRM SSO.

## Current tested limits

Automated tests cover independent-record edits, same-record stale conflict,
idempotent replay, mutation-ID misuse, approved-revision rejection, conflict
resolution, presence expiry, incident membership revocation, server-side field
omission/redaction, denied restricted-field edits, and disabled shadow identity
provisioning.

No safe concurrent-user count or production throughput is established. Before
operational activation, run PostgreSQL deployment-specific synthetic load tests
covering concurrent mutations, audit growth, long incident histories, proxy
timeouts, worker saturation, and failure recovery.
