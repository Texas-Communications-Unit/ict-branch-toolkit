# Asset management

The **Asset Management** workspace provides the first governed inventory and accountable-radio
checkout workflow. It is separate from the ICS 205 planning tabs. This release supports asset
records and parent/child relationships, incident-scoped radio checkout and return, accountability
holds, auditable codeplug-backup attestations, and official ICS 219 accountability reports.

The asset list also provides a print-label action. Labels include the human-readable asset ID,
category, non-sensitive equipment description, and either the parent asset ID or parent/standalone
role. They intentionally exclude driver-license and radio-system information. A scanner operating
as a keyboard wedge can enter an asset ID through the same labeled controls used for manual entry;
no pointer-only scanning path is required.

## Operational inventory records

The workspace supports multi-asset checkout to one individual, including the assigned agency,
24-hour point of contact, phone number, mailing address, and assignment notes. The same accountable
return and driver-license retention rules apply independently to each selected asset.

Inventory operators can search by asset ID, serial number, alias, manufacturer, or model; filter by
category and status; and sort the displayed inventory. Radio metadata includes subtype, flash code,
subscriber ID, system IDs, acquisition date, and the last calibration timestamp. Flash codes and
system identifiers are operational data and must not be copied into public labels or unapproved
exports.

Maintenance records capture the work type, technician, time, notes, and whether the asset was
returned to service. Calibration entries update the asset's last-calibrated timestamp. Charging
records capture start and completion times with an optional note. Creating either record produces
an audit event. A maintenance entry cannot silently make an actively checked-out asset available.

## Bulk asset import

Inventory managers can preview and then commit a CSV or XLSX file from **Bulk import assets**.
Previewing does not create assets. The system displays the first 20 normalized rows, validates the
entire file, and provides a CSV of row-level errors. Commit is unavailable until every row passes.
An import is limited to 500 asset rows and a 5 MiB source file.

The first worksheet is used for XLSX files. CSV files must be UTF-8. Heading capitalization and
spaces are normalized. Required headings are `asset_id` and `category`; supported optional
headings are `parent_asset_id`, `manufacturer`, `model`, `serial_number`, `alias`, `asset_subtype`,
`flash_code`, `subscriber_id`, `system_ids`, `acquisition_date`, `status`, and `notes`. Dates use
`YYYY-MM-DD`. Categories are `radio`, `battery`, `antenna`, `cable`, `microphone`, or `accessory`.
Statuses are `in_service`, `spare`, `maintenance`, or `retired`. A parent may already exist or may
appear elsewhere in the same file. Duplicate IDs, missing parents, and parent cycles are rejected.

The server stores the source name, SHA-256 digest, normalized preview, validation result, operator,
and commit time for accountability. It does not retain the uploaded workbook itself.

## Asset files and photos

**Files and photos** stores records such as receipts, manuals, damage photographs, programming
worksheets, and service documents against an asset. Inventory viewers may list and download files;
inventory managers may upload and delete them. Upload and download events are audited. A deletion
soft-deletes the database record and removes the stored file.

Allowed formats are PDF, UTF-8 TXT/CSV, JPG/JPEG, PNG, WEBP, DOCX, and XLSX. The default limit is
20 MiB per file and can be changed with `ICT_ATTACHMENT_MAX_BYTES`. The server verifies the file
structure instead of trusting the browser's content-type label. Downloads are authenticated,
forced as attachments, marked `nosniff`, and not cached. Do not use asset attachments for passwords,
encryption keys, or other credentials.

Production Compose stores these files in the persistent `attachment-data` volume mounted at
`/app/media`; they are not stored in Git. A database backup alone cannot recover them. Back up the
database and attachment volume as one recovery set by following the
[backup and restore runbook](backup-restore-and-rollback.md#asset-attachment-backup).

## ICS 219 accountability reports

Each incident checkout provides two PDF downloads populated from checksum-pinned official forms:

- **ICS 219-7 Equipment Resource Status Card** is the yellow equipment T-card. It shows the asset,
  assigned person and agency, primary contact, incident, checkout time, current assignment status,
  and equipment identifiers. The official instruction page remains attached.
- **ICS 219-9 WF Accountable Property Assignment Record** shows the asset, current incident
  assignment, return status, and recent maintenance entries.

ICS 219-7 and ICS 219-9 WF are related but distinct forms. The former is the resource-status
T-card; the latter is the NWCG accountable-property card. Both reports are flattened PDFs, and
every download creates an audit event containing the file digest and byte count. Neither report
contains the driver's-license number or mailing address. Operators must review the populated card
before printing because locally required order numbers, operational periods, and routing practices
may differ.

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
7. Download both ICS 219 reports for a synthetic checkout. Confirm the equipment T-card is yellow,
   the accountability record reflects the assignment, and neither PDF contains the test license
   number or mailing address.
8. Preview a synthetic CSV import, verify its displayed rows, correct any reported errors, commit
   it once, and confirm that replaying the same batch is refused.
9. Upload, download, and delete a synthetic attachment. Confirm a read-only inventory user cannot
   upload or delete it and that each completed action appears in the audit log.
