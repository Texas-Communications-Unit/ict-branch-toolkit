# Accessibility standard and definition of done

## Required standard

ICT Branch Toolkit targets conformance with
[WCAG 2.2 Level AA](https://www.w3.org/TR/WCAG22/) across complete user
processes. WCAG 2.2 includes the WCAG 2.1 success criteria and is the project's
engineering baseline for new work and material changes.

The United States Department of Justice's Title II web rule identifies WCAG 2.1
Level AA as the regulatory technical standard for covered state and local
government web content and mobile applications. The project uses WCAG 2.2 Level
AA because it preserves that baseline and adds current W3C criteria. See the
[DOJ Title II rule fact sheet](https://www.ada.gov/resources/2024-03-08-web-rule/).

An automated scan is not a conformance claim. W3C states that evaluation tools
cannot determine every accessibility requirement; required human evaluation is
defined below.

## Scope

The standard applies to:

- sign-in, authenticated planning, administration, error, empty, loading,
  offline, conflict, and permission-change states;
- desktop, mobile, responsive, zoomed, and reflowed presentations;
- keyboard, pointer, touch, speech-input, and assistive-technology workflows;
- maps, charts, color-coded status, drag interactions, and their nonvisual and
  non-pointer equivalents;
- help, validation, timeouts, authentication, notifications, and destructive
  or approval actions;
- downloadable PDFs, SVGs, tables, reports, and other generated content needed
  to complete a Toolkit process;
- extensions, modules, embedded content, and third-party components included in
  a Toolkit-supported process.

## Pull-request definition of done

Every user-facing pull request must meet all applicable requirements:

1. Identify the affected user processes, states, input methods, and generated
   content in the pull-request accessibility impact statement.
2. Use native HTML semantics first. Every control has an accessible name, role,
   value, instructions, programmatic error association, and announced status
   change where applicable.
3. Preserve logical reading and focus order, visible focus, focus that is not
   obscured, a keyboard-only path, and an alternative to dragging or map-only
   interaction.
4. Do not communicate meaning through color, shape, position, sound, or pointer
   location alone.
5. Support text resizing to 200 percent and reflow at 320 CSS pixels without
   document-level two-dimensional scrolling. Data tables and maps may use
   contained scrolling when their accessible equivalent remains available.
6. Keep interactive targets at least 24 by 24 CSS pixels or satisfy a documented
   WCAG 2.2 exception. Toolkit-styled form controls and buttons target 44 by 44
   CSS pixels.
7. Avoid inaccessible authentication steps, repeated entry, unexpected context
   changes, and unannounced errors or time limits.
8. Add or update component and browser tests. Axe must report no violations for
   the applicable WCAG 2.0, 2.1, and 2.2 Level A/AA tags at every materially
   changed checkpoint.
9. Pass the JSX accessibility linter, frontend tests, build, and browser
   accessibility workflow.
10. Update the manual evaluation scope and export review when automation cannot
    decide the applicable success criteria.

Backend-only, documentation-only, and dependency-only changes must state why
they have no user-facing accessibility impact. They must still preserve the
existing checks.

## Automated evidence

Continuous integration enforces:

- `eslint-plugin-jsx-a11y-x` recommended semantic checks for application and test
  JSX;
- axe-core scans tagged `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, and
  `wcag22aa`;
- sign-in and authenticated complete-process checkpoints;
- keyboard order and skip-link behavior;
- a 320-CSS-pixel authenticated viewport with no document-level horizontal
  overflow;
- an attached JSON axe result for each tested checkpoint;
- component, type, lint, format, production-build, and end-to-end regression
  checks.

New routes, dialogs, stateful workflows, and substantially changed components
must be added to the automated checkpoints. Passing CI means only that the
automated evidence passed.

## Required human evidence

Before a release candidate, deployment candidate, or accessibility conformance
claim, a named reviewer must complete
[`docs/templates/accessibility-evaluation.md`](../templates/accessibility-evaluation.md)
against the exact commit and record:

- keyboard-only completion with no trap, inaccessible action, illogical order,
  obscured focus, or pointer-only requirement;
- text resize at 200 percent and reflow/zoom at 400 percent, including 320 CSS
  pixel presentation;
- text, non-text, focus, status, and graphical contrast;
- screen-reader names, roles, values, landmarks, headings, tables, errors,
  status changes, dialogs, and complete-process behavior;
- touch/target size, dragging alternatives, consistent help, redundant-entry,
  and accessible-authentication behavior where applicable;
- reduced motion, orientation, hover/focus content, timeouts, and session
  recovery where applicable;
- generated-content structure, reading order, language, title, alternatives,
  contrast, and keyboard/screen-reader use;
- browser, operating system, assistive-technology versions, findings,
  linked defects, retest results, tester, and date.

Manual testing must use synthetic data. A release cannot reuse evidence from a
different commit when the affected user process or generated output changed.

## Generated content

Browser axe results do not cover downloaded files.

- A PDF intended as an accessible deliverable requires tagged structure,
  correct reading order, document title and language, table headers, meaningful
  link text, text alternatives, and applicable contrast. Verify it with a
  PDF-accessibility checker and a screen reader.
- An SVG or visual map requires equivalent structured text or table data for
  every operationally relevant value and relationship.
- CSV, GeoJSON, and KML support data portability but do not by themselves
  replace an accessible human-readable presentation.
- An accessible web presentation may supplement a generated file, but the
  alternate path must be identified, complete, current, and tested. It must not
  be used to avoid fixing a format that can reasonably be made accessible.

## Defects, exceptions, and release gates

Accessibility defects use the same severity and ownership discipline as
security and data-integrity defects.

- A blocker or critical barrier prevents merge when introduced by the change
  and prevents release or deployment while present in a required process.
- A serious barrier requires a linked issue, accountable owner, documented
  workaround, and maintainer disposition before merge; it blocks a conformance
  claim and normally blocks release.
- Lesser findings require a linked issue and scheduled correction.

An exception must identify the exact WCAG criterion, affected process and
users, technical or legal limitation, accessible workaround, owner, target
date, and approving maintainer. Cost or schedule alone is not an accessibility
exception. The project must not claim WCAG conformance while a known blocker to
that conformance remains open.

## Authoritative references

- [WCAG 2.2](https://www.w3.org/TR/WCAG22/)
- [How to Meet WCAG 2.2](https://www.w3.org/WAI/WCAG22/quickref/)
- [W3C Easy Checks](https://www.w3.org/WAI/test-evaluate/easy-checks/)
- [W3C guidance on evaluation tools](https://www.w3.org/WAI/test-evaluate/tools/selecting/)
- [DOJ Title II web and mobile application rule](https://www.ada.gov/resources/2024-03-08-web-rule/)
