# ADR-0022: Official FEMA ICS 205 export template

- Status: Accepted
- Date: 2026-08-20
- Decision owners: Maintainers

## Context

The initial toolkit export was a deterministic FEMA-style document created with
ReportLab. Field users need the operational output to match the official FEMA ICS
Form 205 v3.1 so the document is immediately recognizable and interoperable with
established Incident Command System workflows.

## Decision

Use the official FEMA ICS Form 205 v3.1 PDF as the export template. Populate its
existing AcroForm fields with approved revision data, flatten the populated page,
remove interactive form widgets, and omit the source document's instruction pages
from the operational output.

The official form provides eight assignment rows. Revisions with more than eight
assignments repeat the form page in eight-row chunks and identify each page in
Special Instructions. The toolkit leaves Zone/Group and signature blank because
those values are not currently represented or captured as signatures. It maps
recognized modes to the official A, D, or M values and retains unrecognized mode
text in Remarks. Preview and publication notices remain visible in Special
Instructions.

Frequency-based assignments retain an explicit channel width. Following FEMA's
two-designator instruction and FCC land-mobile terminology, 6.25 kHz and 12.5
kHz widths render as `N`, while legacy 25 kHz widths render as `W`. The value is
shown after the four-decimal frequency in parentheses, such as `150.0001 (N)`.
The toolkit does not introduce a nonstandard `UW` designator; an unknown width is
left undesignated rather than inferred from the frequency or service.

The official source URL and SHA-256 checksum are pinned beside the template. PDF
tests verify the checksum, deterministic output, official headings, continuation
pages, populated values, and removal of interactive widgets.

## Consequences

Exports now preserve the official form's appearance and terminology. Each page
holds fewer rows than the former custom layout, so larger plans have more pages.
The bundled source PDF increases the application artifact size and must be reviewed
when FEMA publishes a replacement version. The on-screen workspace mirrors the
official form's numbered sections and channel table while retaining toolkit-only
editing, collaboration, publication, and approval controls outside the official
data columns.

## Alternatives considered

Continuing the custom ReportLab layout was rejected because visual similarity did
not meet the operational requirement. Recreating the official form from scratch
was rejected because it would add fidelity and maintenance risk. Keeping populated
AcroForm controls was rejected because immutable approved exports should render
consistently across PDF viewers.
