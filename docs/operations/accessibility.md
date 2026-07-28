# Accessibility review and checks

The ICT Branch Toolkit targets WCAG 2.2 Level AA across complete user
processes. The binding scope, pull-request definition of done, defect
disposition, and exception rules are in the
[accessibility standard](../governance/accessibility-standard.md).

## Automated checks

Frontend linting applies the recommended `eslint-plugin-jsx-a11y-x` rules to
application and test JSX. The Playwright workflow runs axe-core with
`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, and `wcag22aa` tags. It fails when
axe reports a violation and attaches a JSON result for each checkpoint.

The browser workflow currently checks:

- the desktop sign-in screen;
- the authenticated planning workflow on a desktop viewport;
- keyboard order through sign-in;
- the authenticated skip link and focus transfer;
- the map's accessible name, instructions, coordinate form, and structured site
  workflow;
- the authenticated workspace at 320 CSS pixels;
- document-level horizontal overflow at 320 CSS pixels.

Run the checks locally:

```shell
cd frontend
pnpm install --frozen-lockfile
pnpm lint
pnpm test:e2e
```

GitHub Actions runs the same lint and browser commands. A new route, dialog,
complete process, or materially different loading, empty, error, success,
permission, offline, or conflict state must extend the automated checkpoints.

## Human evaluation

Automation cannot decide every WCAG requirement or prove conformance. Before a
release or deployment candidate, copy and complete the
[accessibility evaluation record](../templates/accessibility-evaluation.md)
against the exact commit.

At minimum:

1. Complete all affected processes with keyboard only.
2. Check visible and unobscured focus, order, traps, dialogs, errors, and
   pointer/drag alternatives.
3. Test 200 percent text resize and 400 percent zoom/reflow, including 320 CSS
   pixel presentation and text-spacing overrides.
4. Measure text, non-text, graphical, status, and focus contrast.
5. Complete affected processes with a supported screen reader and record the
   browser, screen reader, operating system, and versions.
6. Verify target sizes, redundant entry, consistent help, and accessible
   authentication where applicable.
7. Review every generated PDF, SVG/map, table, or other artifact needed by the
   process with format-specific tools and assistive technology.
8. Record every finding in a linked issue with criterion, severity, affected
   users/process, owner, workaround, and retest result.

Use synthetic data only. Evidence from a different commit is not sufficient
when the affected process or generated artifact changed.

## Keyboard and screen-reader design

- Forms use native labels and controls.
- Focus has a high-visibility outline and focused elements receive scroll
  margin so author-created content does not place them against an edge.
- Authenticated content begins with a skip link to the planning workspace.
- Immediate status and error messages use live-region semantics.
- The map is a named region linked to instructions.
- Clicking, dragging, and visual layers are optional. Coordinate entry, parsed
  results, radio-site lists, result tables, and explicit actions provide the
  non-pointer and nonvisual workflows.
- Styled buttons and form controls target 44-by-44 CSS pixels; the WCAG 2.2
  Level AA minimum and documented exceptions still govern all other targets.
- Reduced-motion preferences suppress nonessential authored animation and
  transitions.

## Known boundaries

- A clean axe report does not prove WCAG conformance.
- Axe does not evaluate every focus, screen-reader, reflow, cognitive,
  authentication, contrast, motion, or touch requirement.
- The MapLibre canvas is a visual aid. Structured controls and tables are the
  accessible source for planning data and actions.
- Browser checks do not evaluate downloaded PDF, SVG, CSV, KML, or GeoJSON
  files.
- The current release remains blocked until the required human record and
  generated-content review are complete for the exact candidate commit.
