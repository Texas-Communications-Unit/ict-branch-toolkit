# Accessibility review and checks

The ICT Branch Toolkit browser interface targets WCAG 2.1 Level A and AA for
the Phase 1 planning workflow. Accessibility is part of the release gate, not a
substitute for operational acceptance testing.

## Automated checks

The Playwright workflow runs axe-core against both the sign-in screen and the
authenticated planning workspace. It checks WCAG 2.0 and 2.1 Level A and AA
rules and fails when axe reports a violation.

Run the check locally with:

```shell
cd frontend
pnpm test:e2e
```

The end-to-end job in GitHub Actions runs the same command. New pages or
substantially changed workflows must be added to the axe scan.

## Keyboard and screen-reader behavior

- All forms use native labels and controls.
- Keyboard focus has a visible outline.
- The authenticated page begins with a skip link. Activating it moves focus to
  the planning workspace.
- Status and error messages use live-region semantics where immediate
  notification is needed.
- The map is identified as a named region and linked to instructions.
- Map clicking and marker dragging are optional. Coordinate entry, parsed
  coordinate results, the radio site list, and site actions provide the
  non-pointer workflow.

The Playwright test verifies sign-in tab order, skip-link focus transfer, map
instructions, and axe results. Before a non-production release candidate is
approved, a human tester must also complete the primary workflow using only the
keyboard and review it with a supported screen reader such as NVDA.

## Known boundaries

- Automated axe results do not prove conformance or replace testing by people
  who use assistive technology.
- The MapLibre canvas is a visual aid. The coordinate form and radio site list
  are the accessible source of the same planning data.
- Exported PDF and SVG artifacts require their own accessibility review. They
  are not covered by the browser axe scan.

Record manual test date, browser, screen reader, tester, findings, and any
follow-up issue in the release candidate checklist.
