# AGENTS.md

## Mission

Build the ICT Branch Toolkit as a standalone, portable, secure-by-default incident communications planning application.

## Locked requirements

- Preserve the product name **ICT Branch Toolkit**, the short name **ICT Toolkit**, and the GNU AGPL v3 license.
- Preserve this statement: **Originally developed by the Texas Communications Unit (TX-COMU).**
- Keep the application independent of WordPress, CiviCRM, and the TX-COMU website.
- Never commit real incident data, protected channel data, credentials, keys, certificates, private server details, or operational connection information.
- Use only synthetic, public, or explicitly approved reference data.
- Treat coverage and deconfliction output as planning decision support, never as authorization, coordination approval, or a guarantee.

## Engineering rules

- Work in a feature branch. Never commit directly to `main`, merge, deploy, or change DNS without human approval.
- Keep approved or published revisions immutable; changes create a new draft revision.
- Store frequencies as integer hertz, coordinates in WGS 84, and distances canonically in meters.
- Keep conventional channels and trunked talkgroups distinct and retain source/version provenance.
- Put authorization policy in backend permission classes or services, not scattered UI conditionals.
- Add migrations, tests, documentation, and sample configuration with behavioral changes.
- Prefer small, focused commits and reversible decisions. Record material architectural choices as ADRs.
- Run formatting, linting, type checks, tests, builds, migration checks, and security checks before requesting review.

## Current milestone

P1.0 establishes governance, requirements, architecture, a reproducible scaffold, and a thin authenticated incident/operational-period vertical slice. See `docs/requirements/phase-1.md`.

