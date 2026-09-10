# Categorized NIFOG resources

The Resources workspace presents conventional CISA NIFOG channels as expandable categories for field-reference use.

## Data source and grouping

The interface does not contain a second hard-coded list of NIFOG channels. It uses the versioned `ResourceSource` / `ResourceRelease` / `ConventionalChannel` records already imported through the resource library.

For records whose source type is `cisa_nifog`, the category heading is selected in this order:

1. the imported `source_section` value;
2. the imported `channel_use` value when no source section is present;
3. the imported band with an `interoperability channels` label;
4. `Other NIFOG channels` when none of those fields are available.

The fallback labels are presentation-only. They do not infer frequencies, tones, authorizations, or NIFOG technical content.

Each release/section combination is kept separate so channels from different NIFOG releases are not silently merged into a single category.

## Displayed technical fields

Expanded NIFOG categories show the imported values for:

- Assignment (`channel_use`)
- Channel Name and identifier
- Mobile RX frequency
- Mobile RX CTCSS / NAC (`rx_squelch`)
- Mobile TX frequency
- Mobile TX CTCSS / NAC (`tx_squelch`)
- Authorized Emissions (`emission_designator`)
- Other Notes, including imported notes, restrictions, and authorization text

Canonical frequencies remain integer hertz in application data. The reference table displays MHz to six decimal places, which preserves integer-Hz precision without changing the source record.

The category also displays the source name, release version, and imported page reference when available.

## Interaction and accessibility

Categories use native HTML `details` / `summary` disclosure semantics. They are collapsed by default, can be opened independently, and remain keyboard operable without custom key handling.

The technical table uses column headers with `scope="col"`. Wide tables are placed in a named, keyboard-focusable horizontal-scroll region so all columns remain available at narrow viewports and high zoom. Expanded/collapsed state is communicated by native disclosure semantics rather than color alone.

## Search and non-NIFOG resources

The existing Resources search continues to filter conventional records. Categorized results follow that search value. Conventional channels from sources other than CISA NIFOG remain available in a separate `Other conventional reference channels` disclosure. Existing trunked-talkgroup presentation is not replaced.

## Operational limitation

This view is a reference aid. Presence of a channel in NIFOG or in the Toolkit does not by itself authorize transmission, establish licensing eligibility, satisfy coordination requirements, provide encryption authority, or supersede agency or incident policy. Operators should use the source/release/page references to verify governing guidance when needed.
