# Accessibility evaluation record

Copy this file for each release or deployment candidate. Store only synthetic
test details and public environment information.

## Candidate

- Commit SHA:
- Build/version:
- Candidate URL or local build:
- Evaluation date:
- Tester:
- Related pull request:
- Related accessibility issues:

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
- [ ] Coordinate entry, radio sites, assignments, rings, and map alternatives
- [ ] RF profile, HAAT, coverage, and directional-analysis workflows
- [ ] Loading, empty, error, warning, disabled, and success states
- [ ] Generated PDF, SVG/map, table, and applicable data exports
- [ ] Other affected process:

## Keyboard and focus

- [ ] Complete each applicable process with keyboard only.
- [ ] No keyboard trap or pointer/drag-only action is present.
- [ ] Focus order follows the meaningful reading and operation order.
- [ ] Focus is visible, sufficiently contrasted, and not fully obscured.
- [ ] Skip links, dialogs, disclosures, validation, and destructive actions work.
- [ ] Focus returns to a logical location after dialogs, errors, or removed UI.

Findings:

## Resize, zoom, reflow, and orientation

- [ ] Text remains usable at 200 percent.
- [ ] Content reflows at 400 percent/320 CSS pixels without document-level
      two-dimensional scrolling.
- [ ] Contained table or map scrolling does not hide an accessible equivalent.
- [ ] Portrait and landscape presentations preserve content and operation.
- [ ] Text-spacing overrides do not clip, overlap, or remove content.

Findings:

## Visual presentation and motion

- [ ] Text and large-text contrast meet Level AA.
- [ ] Controls, focus, graphics, and status boundaries meet non-text contrast.
- [ ] Color, shape, position, or sound is not the only source of meaning.
- [ ] Hover/focus content can be dismissed, hovered, and persisted as required.
- [ ] Reduced-motion preference avoids nonessential motion.
- [ ] Flashing or animation does not create a seizure or vestibular risk.

Contrast tool and results:

Findings:

## Screen reader and semantics

- [ ] Page title, language, landmarks, headings, lists, and reading order are
      meaningful.
- [ ] Controls expose accurate names, roles, values, instructions, and states.
- [ ] Required fields and errors are programmatically identified and explained.
- [ ] Status, warning, validation, loading, and session messages are announced.
- [ ] Tables expose captions, headers, and cell relationships.
- [ ] Maps, charts, layers, and graphical results have complete structured
      alternatives.
- [ ] Dialogs and disclosures announce state and manage focus correctly.

Screen-reader process notes:

Findings:

## WCAG 2.2 interaction checks

- [ ] Focus is not obscured by author-created content.
- [ ] Dragging has a single-pointer or keyboard alternative.
- [ ] Targets meet 24-by-24 CSS pixels or a documented exception.
- [ ] Help appears consistently when provided.
- [ ] Previously entered information is not unnecessarily requested again.
- [ ] Authentication does not depend on memory, transcription, puzzles, or
      another cognitive-function test without an accessible alternative.

Findings:

## Generated content

| Artifact             | Checker and result | Screen-reader/keyboard result | Defect or limitation |
| -------------------- | ------------------ | ----------------------------- | -------------------- |
| PDF                  |                    |                               |                      |
| SVG/map              |                    |                               |                      |
| Tabular presentation |                    |                               |                      |
| Other                |                    |                               |                      |

- [ ] PDF title, language, tags, headings, lists, table headers, reading order,
      links, alternatives, and contrast were checked.
- [ ] Every visual export has a complete, current, discoverable structured
      alternative.
- [ ] Accessible alternatives were compared with the exact generated artifact
      and contain the same operationally relevant information.

## Findings and disposition

| Severity | WCAG criterion | Process/users affected | Issue | Owner | Workaround | Retest |
| -------- | -------------- | ---------------------- | ----- | ----- | ---------- | ------ |
|          |                |                        |       |       |            |        |

## Decision

- [ ] Automated evidence passed for the exact commit.
- [ ] Required human checks passed.
- [ ] Generated-content checks passed.
- [ ] No unresolved blocker, critical, or serious barrier remains in a required
      process.

Decision: Pass / Fail / Blocked

Reviewer name and date:

Maintainer acceptance and date:
