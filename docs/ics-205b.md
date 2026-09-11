# ICS 205B — Incident Information Management Plan

The **ICS 205B** workspace supports Information Technology Service Unit Leader (ITSL) planning for incident information-technology infrastructure and services.

## Form basis

The implementation is based on the user-provided workbook `ICS 205B Blank.xlsx`. The visible template identifies itself as **ICS Form 205b** with **Form Revision: 6/15/2018**. The Toolkit preserves those labels in generated exports but does not make an independent claim that the uploaded workbook is a current federal form or that use of the form satisfies any agency-specific requirement.

The form contains:

1. Incident Name
2. Date/Time Prepared
3. Operational Period Date/Time
4. Information Technology Infrastructure & Services Assignment
5. Prepared By (Name and Position), Phone Number, Signature, and Date/Time
6. Incident Location, State, County, and City

The assignment table preserves the ten source columns: Assignment; IT Resource Type; Name of Application or Resource; Usage or Description; Platform; Developer; Login/Install; Equipment Location / Web Address, IP Address or SSID; POC Information; and Remarks.

## Incident and operational-period scope

One ICS 205B is stored for each incident/operational-period pair. The incident name and operational-period start/end values come from the canonical incident records. Prepared date/time, preparer information, location information, and assignment rows are stored on the ICS 205B record.

The form reuses the Toolkit's existing incident-scoped plan permissions:

- `plan.view` to view the form;
- `plan.edit` to create or edit the form and its rows; and
- `plan.export` to download Excel or PDF output.

All successful changes and exports are recorded in the append-only audit log. Export events include the SHA-256 digest and byte length of the exact returned file.

## Credential and sensitive-data handling

The template includes a **Login/Install** field. This field is intended for installation instructions, approved login method descriptions, account identifiers, or similar operational notes. **Do not store passwords, API keys, access tokens, private keys, certificates, recovery codes, or other authentication secrets in ICS 205B.**

The Equipment Location / Web Address, IP Address or SSID and POC Information fields may contain operationally sensitive information. Operators should apply incident policy, least disclosure, and applicable records/security requirements before entering or exporting those values.

## Excel export

The `.xlsx` exporter recreates the supplied 29-row landscape form structure with the original visible headings, assignment columns, footer labels, and revision line.

The source template provides 21 assignment rows per printable page. The Toolkit therefore emits up to 21 assignments on each worksheet page. If more than 21 assignments exist, additional continuation worksheets are created. Each continuation worksheet repeats:

- the ICS 205B title;
- incident name;
- prepared date/time;
- operational-period dates/times;
- section 4 heading and assignment-column headings;
- prepared-by and incident-location footer information;
- `ICS Form 205b`;
- `Form Revision: 6/15/2018`; and
- a page-number footer.

Sheets use letter-size landscape print settings, a defined A1:K29 print area, fit-to-page scaling, and page margins modeled on the supplied workbook.

## PDF export

The PDF export is generated from the same stored ICS 205B record used by Excel export. It uses landscape letter pages and a repeating assignment-table header.

On every PDF page the Toolkit repeats the identifying header and footer information, including the incident, prepared date/time, operational period, prepared-by/location fields, form name, and form revision. Every page is labeled **Page X of Y**. Long assignment-cell content wraps instead of being clipped and may increase row height or continue the table onto later pages.

## Accessibility

The web workspace provides a semantic HTML table as the non-document representation of all assignment data. Incident and operational-period selectors, edit controls, row actions, form fields, and export buttons are keyboard operable and remain subject to the project-wide WCAG 2.2 AA engineering requirements in Issue #61. Generated documents remain part of the project's required human accessibility evaluation; automated tests alone do not establish document accessibility conformance.

## Validation and testing

Synthetic automated coverage includes:

- incident/operational-period validation;
- assignment creation, update, deletion, and stable ordering;
- authorization checks;
- Excel generation with enough rows to require multiple continuation sheets;
- repeated Excel form identity, revision, and page numbering;
- PDF generation with enough content to force multiple pages;
- repeated PDF header/footer information and `Page X of Y`; and
- audit evidence for exports.

No real incident, credential, private infrastructure, or protected operational data is used in automated tests.
