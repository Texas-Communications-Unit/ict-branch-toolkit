# ICT Branch Toolkit <version> — NON-PRODUCTION PROTOTYPE RELEASE CANDIDATE

> **NOT PRODUCTION READY — SYNTHETIC DATA ONLY**
>
> This release candidate is for controlled evaluation. It is not a supported
> production release, deployment authorization, or approval to use real
> incident, protected channel, personal, credential, or private infrastructure
> data.

## Candidate identity

- Version and RC number: `<version>`
- Annotated tag: `<tag>`
- Full commit SHA: `<40-character-sha>`
- Source archive SHA-256: `<sha256>`
- SBOM format, generator, version, and SHA-256: `<details>`
- Verification date: `<YYYY-MM-DD>`

## Evaluation scope

Summarize the reviewed capabilities and the Issue #7 acceptance items included
in this candidate. Link the exact pull requests and do not claim work that is
still pending.

## Installation and operation

- [Installation and configuration](../../operations/installation-and-configuration.md)
- [Operation and monitoring](../../operations/operation-and-monitoring.md)
- [Backup, restore, upgrade, and rollback](../../operations/backup-restore-and-rollback.md)
- [Security policy](../../../SECURITY.md)

State the evaluated operating system, Docker/Compose versions, browser versions,
configuration profile, and synthetic dataset. Do not include private host names,
addresses, paths, secrets, or operational connection information.

## Verification evidence

Link results for the exact commit:

- CI and container build:
- Security, dependency, secret, static, container, and composition checks:
- Accessibility automation and human review:
- Authentication, authorization, error handling, and rate-limit checks:
- Audit-chain and abuse-case review:
- Performance test report and tested limits:
- Backup, restore drill, upgrade, rollback, and recovery:
- Clean installation and synthetic operator smoke test:

## Known limitations and blocked uses

List every accepted limitation, including authentication/token lifecycle,
monitoring, external providers, retention, audit anchoring, tested capacity, and
unsupported integrations. State plainly that:

- the candidate accepts synthetic data only;
- coverage and deconfliction output is planning decision support, not
  authorization, coordination approval, propagation study, or guarantee;
- no production-supported version or production service-level objective exists;
- publication does not authorize deployment or non-synthetic data.

## Human approvals

- Maintainer, decision, and date:
- Security reviewer, decision, and date:
- Operations reviewer, decision, and date:
- Accessibility reviewer, decision, and date:
- Qualified communications reviewer, decision, and date:
- Separate synthetic shared-test deployment approval, if any:

## License and attribution

ICT Branch Toolkit is licensed under the
[GNU Affero General Public License v3.0](../../../LICENSE).

Originally developed by the Texas Communications Unit (TX-COMU).
