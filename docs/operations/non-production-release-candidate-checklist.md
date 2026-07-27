# Non-production release candidate checklist

This checklist controls preparation and human acceptance of an ICT Branch Toolkit
Phase 1 release candidate. A candidate remains a **non-production prototype** for
synthetic, public, or explicitly approved reference data only. Creating a tag or
GitHub Release does not authorize deployment, operational use, real incident
data, or a production support commitment.

The release manager records evidence in the candidate pull request or release
record. A checked box without a link, command result, artifact, or named human
acceptor is not sufficient evidence.

## Candidate identity and scope

- [ ] The candidate commit is on the reviewed `main` history and is recorded by
      full SHA.
- [ ] The proposed version and tag identify the build as a pre-release, for
      example `v0.1.0-rc.1`.
- [ ] The GitHub Release is marked **pre-release** and its title and notes say
      **non-production prototype**.
- [ ] The release notes enumerate the Phase 1 capabilities actually present and
      do not claim deferred P1.4 deconfliction, propagation analysis, coordination
      approval, spectrum authorization, or guaranteed coverage.
- [ ] All included issues and pull requests are linked, and every known excluded
      or deferred criterion is listed.
- [ ] The permanent product name, GNU AGPL v3 license, and statement
      "Originally developed by the Texas Communications Unit (TX-COMU)." remain
      present.
- [ ] No release artifact depends on WordPress, CiviCRM, or the TX-COMU website.

## Repository and change-control evidence

- [ ] The candidate working tree is clean and the candidate SHA exactly matches
      the reviewed commit.
- [ ] Required branch protections, reviews, and human approvals remain in force.
- [ ] Migrations between the previous reviewed checkpoint and the candidate are
      listed with reversibility or backup-and-restore treatment.
- [ ] Configuration changes are documented in `.env.example` and the operations
      documentation without secret values.
- [ ] Material architecture or behavior decisions have an ADR when required.
- [ ] Generated OpenAPI and other checked-in generated artifacts reproduce
      exactly from the candidate commit.
- [ ] Release notes identify any incompatible API, data-model, configuration, or
      operator-workflow change.

## Automated verification

Record the exact run URL and commit SHA for each required workflow.

- [ ] Backend formatting and linting pass.
- [ ] Django system checks and migration-drift checks pass.
- [ ] Backend unit and integration tests pass with the expected database path.
- [ ] PostgreSQL/PostGIS migrations and integration checks pass.
- [ ] OpenAPI generation, validation, and reproducibility checks pass.
- [ ] Frontend formatting, linting, type checks, unit/component tests, and
      production build pass.
- [ ] Browser end-to-end tests pass using synthetic data.
- [ ] Docker Compose validation and backend/frontend container builds pass.
- [ ] Python and JavaScript dependency audits pass or every exception has a
      linked, time-bounded maintainer decision.
- [ ] Secret scanning, static analysis, container scanning, and software
      composition checks pass or every exception has a linked, time-bounded
      maintainer decision.
- [ ] No required job is cancelled, skipped, still queued, or inferred from a
      prior commit.

## Security, authorization, and data handling

- [ ] Tests cover anonymous, read-only, contributor, COML/COMC/COMT, and
      administrator boundaries applicable to the implemented endpoints.
- [ ] Incident-scoped authorization tests cover cross-incident denial.
- [ ] Authentication and token-lifecycle limitations are documented and
      accepted for the non-production candidate.
- [ ] Rate limits, secure headers, generic error responses, and server-side
      exception logging are verified.
- [ ] Approved or published revisions remain immutable and subsequent edits
      create a new draft revision.
- [ ] Export endpoints reject drafts and use approval-time snapshots.
- [ ] Append-only audit behavior and chain verification pass their tests.
- [ ] Security abuse-case review findings are resolved, explicitly accepted, or
      linked to blocking follow-up work.
- [ ] Repository files, logs, screenshots, reports, and artifacts have been
      reviewed for credentials, personal information, protected channel data,
      real incident data, private endpoints, and operational connection details.
- [ ] Only synthetic, public, or explicitly approved reference data was used.

## Accessibility acceptance

- [ ] Automated axe-core checks pass on sign-in and authenticated planning
      workflows.
- [ ] Keyboard-only navigation, visible focus, skip navigation, dialogs, maps,
      forms, tables, and error recovery have been reviewed.
- [ ] Screen-reader output, names, roles, states, validation messages, and status
      announcements have been reviewed by a named human acceptor.
- [ ] Coordinate and site workflows retain a non-pointer alternative.
- [ ] Known accessibility limitations are documented with severity, workaround,
      owner, and follow-up issue.

Automated checks support but do not replace the required human keyboard and
screen-reader review.

## Performance and tested limits

- [ ] Representative synthetic workload definitions, fixture sizes, hardware or
      runner characteristics, database mode, concurrency, and warm-up method are
      recorded.
- [ ] Response-time, throughput, failure-rate, memory, and artifact-size results
      are published for the workflows the prototype claims to support.
- [ ] Tested upper bounds are stated as measured prototype limits, not capacity
      guarantees.
- [ ] Export generation and browser interaction remain usable at the published
      fixture sizes.
- [ ] Any limit breach has a linked blocking decision or clearly documented
      reduction in candidate scope.

## Backup, recovery, upgrade, and rollback

- [ ] A candidate database backup is created from synthetic test data.
- [ ] Its SHA-256 checksum and archive catalog verify successfully.
- [ ] The backup restores into an isolated database and the restored migration,
      PostGIS, and synthetic marker checks pass.
- [ ] Upgrade steps from the prior reviewed checkpoint are rehearsed with
      synthetic data.
- [ ] Application and migration rollback follow the documented
      backup-and-restore procedure; unsafe reverse-migration assumptions are not
      used.
- [ ] Recovery objectives, encrypted-storage requirements, retention, operator
      roles, and evidence handling are reviewed.
- [ ] No restore, upgrade, rollback, or deployment command is run against a
      shared or operational environment without its separate human gate.

Follow
[backup, restore, upgrade, and rollback](backup-restore-and-rollback.md) for the
controlled procedures. A successful CI restore drill does not authorize a shared
environment restore.

## Installation and operator documentation

- [ ] A new contributor can follow the documented local installation from a
      clean checkout.
- [ ] Configuration, health checks, logs, monitoring, normal operation,
      troubleshooting, upgrade, rollback, and recovery documentation matches the
      candidate.
- [ ] External maps, geocoders, FCCInfo, hosted providers, and other optional
      services remain disabled by default unless their separate provenance,
      licensing, privacy, reliability, and human gates are complete.
- [ ] Public-reference imports identify the exact source, version, digest,
      extraction method, permitted-use boundary, and human approval.
- [ ] Operator documentation distinguishes planning assistance from
      authorization, coordination approval, spectrum licensing, and coverage
      guarantees.

## Human acceptance and release record

The following approvals are independent of CI and must identify the reviewer and
date.

- [ ] A maintainer accepts repository scope, release notes, and unresolved
      limitations.
- [ ] A qualified security reviewer accepts the threat, authorization, audit,
      dependency, and abuse-case evidence.
- [ ] An accessibility reviewer accepts the keyboard and screen-reader evidence.
- [ ] An operations reviewer accepts installation, monitoring, backup, recovery,
      upgrade, rollback, and published performance limits.
- [ ] A qualified incident communications practitioner accepts any operational
      semantics represented by the candidate.
- [ ] Any data-source, mapping-provider, FCCInfo, NIFOG, or other third-party
      human gate applicable to included functionality is separately recorded.
- [ ] The final record links the candidate commit, workflow runs, test artifacts,
      rendered screenshots or PDFs where applicable, limitations, approvals, and
      rollback reference.

## Publication and post-publication

Only a maintainer publishes the tag or GitHub pre-release after every required
gate above is satisfied or explicitly recorded as a blocker.

- [ ] The tag points to the accepted candidate SHA.
- [ ] Release artifacts are reproducible from that SHA and contain no secrets or
      operational data.
- [ ] Checksums are published for downloadable artifacts where applicable.
- [ ] The release is visibly marked pre-release and non-production.
- [ ] Publication does not trigger or imply deployment.
- [ ] A rollback or withdrawal decision owner is named.
- [ ] Newly discovered security issues use private vulnerability reporting when
      they cannot be safely demonstrated with synthetic data.

If a required gate fails, stop publication, preserve the evidence safely, return
the issue to the appropriate review or blocked state, and link the exact follow-up
decision. Do not weaken a check or remove a human gate to make a candidate pass.
