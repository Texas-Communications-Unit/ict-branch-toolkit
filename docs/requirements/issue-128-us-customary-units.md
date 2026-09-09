# Issue #128 — US customary companion units

FCC and other authoritative reference records retain their canonical source values and units. US customary values are presentation-only companions and must never be written back to imported records.

## Conversion constants

- `1 meter = 3.280839895013123 feet`
- `1 mile = 1609.344 meters`
- `1 mile = 1.609344 kilometers`

These constants are exact consequences of the international yard and pound agreement and are centralized in `frontend/src/unitFormatting.ts` rather than repeated in UI components.

## Display and rounding

- Heights display US customary first: whole feet rounded to the nearest foot, followed by the metric source value in parentheses. Example: `328 ft (100 m)`.
- Distances represented in meters or kilometers display miles to two decimal places, followed by the metric source value and explicit source unit in parentheses.
- Metric companion values are displayed to no more than three decimal places, with trailing zeros removed. This is presentation rounding only; source data is unchanged.
- Zero is a valid value and is displayed as zero, not as unavailable.
- Null, blank, non-finite, or otherwise unparseable values display `Not listed`; no conversion is attempted when the source unit or meaning is unknown.

## Accessibility

The customary and metric values are emitted as one ordinary text value with explicit unit abbreviations. Screen readers therefore announce one coherent measurement rather than separate visually-associated fragments. No meaning depends on color, tooltip text, or visual position.

## API boundary

Existing FCC API fields remain explicitly unit-labeled, such as `overall_height_m` and `ground_elevation_m`. This issue does not add ambiguous unlabeled derived numeric fields and does not alter integer-hertz frequency handling.
