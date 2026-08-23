# Asset management

The **Asset Management** workspace provides the first governed inventory and accountable-radio
checkout workflow. It is separate from the ICS 205 planning tabs. This release supports asset
records and parent/child relationships, incident-scoped radio checkout and return, accountability
holds, and auditable codeplug-backup attestations.

The asset list also provides a print-label action. Labels include the human-readable asset ID,
category, non-sensitive equipment description, and either the parent asset ID or parent/standalone
role. They intentionally exclude driver-license and radio-system information. A scanner operating
as a keyboard wedge can enter an asset ID through the same labeled controls used for manual entry;
no pointer-only scanning path is required.

## Driver-license handling

- An issuing state and number are required before a radio can be checked out.
- The number is encrypted by the backend before it is stored. It is never included in labels,
  URLs, ordinary inventory searches or exports, email, application logs, or audit-event details.
- Any authenticated user authorized for the selected incident can view the full number while it is
  retained. Each checkout-list or checkout-detail view creates an audit event without the number.
- A normal undamaged return immediately deletes the encrypted value and its last-four helper.
- A damaged, lost/not-returned, or disputed transaction creates an accountability hold and retains
  the encrypted value. Resolving the hold records the responsible user and UTC time, sets the final
  asset status, and deletes both stored license fields.

The jurisdiction rules are input-quality checks only. They do not verify identity or establish that
a license is valid.

## Codeplug backup attestation

A programming record cannot be completed unless **Codeplug backup saved** is checked. The system
records the confirming user and UTC timestamp. The optional note may identify an approved external
procedure, but must not contain a credential, public share, subscriber identifier, encryption key,
or protected system detail. The Toolkit does not upload or verify the backup in this release.

## Operator checks

1. Verify `ICT_INVENTORY_ENCRYPTION_KEY` is present in the protected deployment environment before
   applying the migration.
2. Select a synthetic incident and verify an inventory manager can add a radio and check it out.
3. Verify an incident read-only member can see the checkout, while a user outside the incident
   cannot.
4. Return one synthetic checkout normally and confirm the displayed number changes to
   **Deleted after return**.
5. Place another synthetic checkout on hold, resolve it, and confirm the number is deleted only at
   resolution.
6. Review the audit log for view, checkout, return/hold, hold-resolution, and programming-attestation
   events. Confirm no test license number appears in event details.
