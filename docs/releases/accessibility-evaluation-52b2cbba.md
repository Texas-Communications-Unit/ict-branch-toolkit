# Accessibility evaluation record — candidate 52b2cbba

This record is prepared for the manual evaluation required by Issues #69 and #61.
It is intentionally **not** a WCAG conformance statement and does not mark human checks
as passed before they are actually performed.

## Candidate

- Commit SHA: `52b2cbba516f3e7c77cdcd22480d93cf2858880b`
- Build/version: current `main` candidate after PR #160
- Candidate URL or local build: to be recorded by evaluator
- Evaluation date: to be recorded by evaluator
- Tester: to be recorded by evaluator
- Related pull request: #160 (latest merged user-facing change before this candidate)
- Related accessibility issues: #61, #69, #125, #130, #148

## Candidate scope

The evaluation must cover the complete current application, including the recently integrated
map/reference workflow and categorized NIFOG Resources interface. Use synthetic data only.

The candidate includes, among other existing workflows:

- authentication and session handling;
- incident and operational-period management;
- ICS 205 planning and generated outputs;
- map location search and coordinate parsing;
- incident radio sites and FCC/reference map objects;
- synchronized map/non-map selection and details;
- FCC companion units and exact NIFOG frequency enrichment;
- categorized NIFOG Resources disclosures and wide technical tables;
- RF analysis, HAAT, coverage, terrain, and validation workflows;
- extension and export workflows already present in the current release candidate.

## Test environment

| Item                   | Version or value |
| ---------------------- | ---------------- |
| Operating system       |                  |
| Browser                |                  |
| Screen reader          |                  |
| Display resolution     |                  |
| Browser zoom/text size |                  |
| Pointer/touch device   |                  |
| Automated workflow run |                  |

## Processes and states evaluated

- [ ] Sign in, authentication error, session expiration, and sign out
- [ ] Incident selection, creation, archive, and permission-restricted states
- [ ] Operational period and ICS-205 planning, validation, approval, and copy
- [ ] Channel and talkgroup reference workflows
- [ ] Categorized NIFOG Resources disclosures, tables, source/version text, and search interaction
- [ ] Coordinate entry, local/external location-search states, radio sites, assignments, rings, and map alternatives
- [ ] FCC map/reference selection synchronization, details, NIFOG enrichment, and companion units
- [ ] RF profile, HAAT, coverage, directional-analysis, terrain, and validation workflows
- [ ] Loading, empty, error, warning, disabled, and success states
- [ ] Generated PDF, SVG/map, table, and applicable data exports
- [ ] Other affected process:

## Keyboard and focus

- [ ] Complete each applicable process with keyboard only.
- [ ] No keyboard trap or pointer/drag-only action is present.
- [ ] Focus order follows the meaningful reading and operation order.
- [ ] Focus is visible, sufficiently contrasted, and not fully obscured.
- [ ] Skip links, dialogs, disclosures, validation, and destructive actions work.
- [ ] Map-object selection has an equivalent non-map keyboard path.
- [ ] NIFOG category disclosures operate with native keyboard semantics and do not unexpectedly move focus.
- [ ] Focus returns to a logical location after dialogs, errors, closed callouts, or removed UI.

Findings:

## Resize, zoom, reflow, and orientation

- [ ] Text remains usable at 200 percent.
- [ ] Content reflows at 400 percent/320 CSS pixels without document-level two-dimensional scrolling.
- [ ] Contained technical-table or map scrolling does not hide an accessible equivalent.
- [ ] Categorized NIFOG tables remain keyboard reachable when horizontal scrolling is required.
- [ ] Portrait and landscape presentations preserve content and operation.
- [ ] Text-spacing overrides do not clip, overlap, or remove content.

Findings:

## Visual presentation and motion

- [ ] Text and large-text contrast meet Level AA.
- [ ] Controls, focus, graphics, and status boundaries meet non-text contrast.
- [ ] Selection, NIFOG-match, warning, disclosure, and status meaning is not communicated by color alone.
- [ ] Hover/focus content can be dismissed, hovered, and persisted as required.
- [ ] Reduced-motion preference avoids nonessential motion.
- [ ] Flashing or animation does not create a seizure or vestibular risk.

Contrast tool and results:

Findings:

## Screen reader and semantics

- [ ] Page title, language, landmarks, headings, lists, and reading order are meaningful.
- [ ] Controls expose accurate names, roles, values, instructions, and states.
- [ ] Required fields and errors are programmatically identified and explained.
- [ ] Status, warning, validation, loading, and session messages are announced.
- [ ] Tables expose captions, headers, and cell relationships.
- [ ] NIFOG category disclosures announce expanded/collapsed state and their table content coherently.
- [ ] Maps, FCC/NIFOG details, charts, layers, and graphical results have complete structured alternatives.
- [ ] Dialogs, callouts, and disclosures announce state and manage focus correctly.

Screen-reader process notes:

Findings:

## WCAG 2.2 interaction checks

- [ ] Focus is not obscured by author-created content.
- [ ] Dragging has a single-pointer or keyboard alternative.
- [ ] Targets meet 24-by-24 CSS pixels or a documented exception.
- [ ] Help appears consistently when provided.
- [ ] Previously entered information is not unnecessarily requested again.
- [ ] Authentication does not depend on memory, transcription, puzzles, or another cognitive-function test without an accessible alternative.

Findings:

## Generated content

| Artifact             | Checker and result | Screen-reader/keyboard result | Defect or limitation |
| -------------------- | ------------------ | ----------------------------- | -------------------- |
| PDF                  |                    |                               |                      |
| SVG/map              |                    |                               |                      |
| Tabular presentation |                    |                               |                      |
| Other                |                    |                               |                      |

- [ ] PDF title, language, tags, headings, lists, table headers, reading order, links, alternatives, and contrast were checked.
- [ ] Every visual export has a complete, current, discoverable structured alternative.
- [ ] Accessible alternatives were compared with the exact generated artifact and contain the same operationally relevant information.

## Findings and disposition

| Severity | WCAG criterion | Process/users affected | Issue | Owner | Workaround | Retest |
| -------- | -------------- | ---------------------- | ----- | ----- | ---------- | ------ |
|          |                |                        |       |       |            |        |

## Operational review notes for #125

This accessibility record may be used alongside, but must not replace, the qualified
COML/COMT/COMC-or-equivalent operational review required by #125/#130. Record any map,
FCC, unit, NIFOG, or workflow interpretation concern in a linked issue before #125 is closed.

Operational reviewer:

Review date:

Findings:

## Decision

- [ ] Automated evidence passed for the exact commit.
- [ ] Required human keyboard/zoom/reflow/contrast checks passed.
- [ ] Required screen-reader checks passed.
- [ ] Generated-content checks passed.
- [ ] Qualified incident-communications review for #125 passed.
- [ ] No unresolved blocker, critical, or serious barrier remains in a required process.

Decision: **Blocked pending human evaluation**

Reviewer name and date:

Maintainer acceptance and date:
