# Non-production prototype release-candidate process

> **NOT PRODUCTION READY — SYNTHETIC DATA ONLY**
>
> A release candidate (RC) is a fixed build offered for controlled evaluation.
> It is not a supported production release, an authorization to deploy, or an
> approval to use real incident, protected channel, personal, credential, or
> private infrastructure data.

This process converts one reviewed commit into an identifiable, verifiable
evaluation candidate. It does not create a release automatically. Maintainers
must approve every merge, tag, GitHub prerelease, and deployment as separate
actions.

## Candidate identity and immutability

Use the planned version followed by `-rc.<number>`, for example
`<planned-version>-rc.1`. The candidate record must identify:

- the full 40-character commit SHA;
- the annotated tag, if a maintainer approves creating one;
- the version reported by the backend, OpenAPI document, Python package, and
  frontend package;
- the exact CI and security workflow runs for that commit;
- source-artifact and software bill of materials (SBOM) SHA-256 digests;
- the completed checklist and named human approvals.

Never move or recreate a published RC tag. A change after candidate approval
requires a new commit and the next RC number. A branch, pull request, draft
release, workflow artifact, or mutable container tag is not a durable candidate
identity.

## Required human roles and gates

- **Maintainer:** accepts scope, reviews the exact diff, approves merge, and
  separately authorizes any tag, prerelease, or deployment.
- **Security reviewer:** accepts the threat model, authentication limitations,
  audit abuse cases, dependency/composition results, and unresolved risk.
- **Operations reviewer:** verifies installation, configuration, monitoring,
  backup, restore, upgrade, rollback, and recovery evidence.
- **Accessibility reviewer:** completes the documented keyboard and assistive
  technology checks.
- **Qualified communications reviewer:** accepts operational semantics and the
  planning-decision-support limitations where affected.

One person may fill more than one role when local policy permits, but every
decision must be explicit. Security and operational acceptance are mandatory
before any hosted test could separately request permission for non-synthetic
data. This RC process itself never grants that permission.

## Release checklist

Do not mark an item complete from assumption, a different commit, or a prior
candidate. Link the evidence for the exact candidate commit.

### Scope and version

- [ ] Issue #7 and every human comment were re-read and mapped to evidence or a
      documented limitation.
- [ ] All required predecessor work is merged and the candidate diff contains
      only reviewed changes.
- [ ] The working tree is clean and the full candidate commit SHA is recorded.
- [ ] Backend runtime, OpenAPI, Python package, and frontend package versions
      agree with the planned RC version or a reviewed exception is documented.
- [ ] Release notes use the
      [non-production RC template](templates/non-production-prototype-rc-notes.md)
      and lead with the required warning.

### Data, privacy, and operational boundaries

- [ ] Repository, fixtures, screenshots, logs, reports, and artifacts were
      reviewed for secrets and non-synthetic or private operational data.
- [ ] Only synthetic, public, or explicitly approved reference data is present,
      with source, version, URL, digest, permission, and human approval recorded.
- [ ] No database dump, protected environment file, credential, key,
      certificate, private host detail, or operational connection information is
      attached.
- [ ] Planning outputs remain labeled as decision support rather than
      authorization, coordination approval, propagation study, or guarantee.
- [ ] Known authentication, audit, privacy, retention, integration, and
      production-readiness limitations are stated in the release notes.

### Verification for the exact commit

- [ ] Formatting, linting, type checks, unit/integration tests, end-to-end tests,
      builds, migration drift checks, OpenAPI validation, and container builds
      pass.
- [ ] Dependency audit, secret scanning, static analysis, container scanning,
      and software-composition analysis pass or every finding has a documented
      maintainer and security disposition.
- [ ] WCAG 2.2 Level AA automated checks pass and the completed
      [accessibility evaluation record](../templates/accessibility-evaluation.md)
      documents keyboard, zoom/reflow, contrast, screen-reader, and
      generated-content review for the exact commit.
- [ ] Authentication/token lifecycle behavior, secure headers, HTTPS/HSTS,
      rate limits, generic error handling, and incident-scoped authorization are
      tested and their remaining limitations accepted.
- [ ] Append-only and hash-chain audit tests plus documented abuse cases pass;
      a manual audit-chain check succeeds on the evaluation installation.
- [ ] Representative performance tests and tested limits are published for the
      candidate environment, dataset, concurrency, duration, and tool versions.
      Untested production capacity is not inferred.
- [ ] A clean installation from the candidate source artifact passes the
      [installation verification](../operations/installation-and-configuration.md#installation-verification).
- [ ] A fresh backup, checksum verification, and isolated restore drill pass
      under the
      [recovery runbook](../operations/backup-restore-and-rollback.md).
- [ ] Upgrade and application/migration rollback have been rehearsed with
      synthetic data, including the previous approved commit and pre-upgrade
      backup.
- [ ] Routine monitoring, log review, account revocation, and security
      escalation were exercised under the
      [operations runbook](../operations/operation-and-monitoring.md).

### Artifacts and provenance

- [ ] The source archive was generated from the approved tag or exact commit in
      a clean environment and expands beneath one versioned top-level directory.
- [ ] SHA-256 checksums cover every published downloadable artifact.
- [ ] An SPDX or CycloneDX SBOM was generated by the approved, version-pinned
      process and its checksum is recorded.
- [ ] Artifact contents were inspected after creation; no working-tree-only
      file, secret, dump, log, cache, or private configuration is included.
- [ ] Release notes link the exact commit, checklist evidence, security policy,
      installation guide, operations guide, recovery runbook, and license.
- [ ] The release title and every optional container/image label include
      `NON-PRODUCTION PROTOTYPE RELEASE CANDIDATE`.
- [ ] Any container reference uses an immutable digest. Publishing containers is
      optional and requires a separate reviewed workflow and registry approval.

### Approval and publication

- [ ] Maintainer approval is recorded for the exact commit and candidate number.
- [ ] Security, operations, accessibility, and applicable communications-domain
      reviews are recorded.
- [ ] Any unresolved acceptance item is explicitly marked as a blocker; the
      candidate is not published while a required item remains incomplete.
- [ ] The annotated tag, if approved, points to the recorded commit and has not
      previously existed.
- [ ] The GitHub release is marked **Pre-release**, uses the required title and
      warning, and contains only verified artifacts.
- [ ] Publication and deployment approvals are treated separately. Any
      synthetic shared-test deployment uses the protected environment gate.
- [ ] No production release, production-support statement, non-synthetic data
      approval, or general deployment authorization is implied.

## Artifact procedure

After all pre-tag checks and human approvals pass, a maintainer may create an
annotated RC tag. Build the source archive from that immutable reference in a
clean environment; do not package the working directory.

```sh
version="v0.0.0-rc.0"
approved_commit="<approved-40-character-commit>"
test "$(git cat-file -t "$version")" = "tag"
test "$(git rev-parse "$version^{commit}")" = "$approved_commit"
git archive \
  --format=tar.gz \
  --prefix="ict-branch-toolkit-$version/" \
  --output="ict-branch-toolkit-$version-source.tar.gz" \
  "$version"
sha256sum "ict-branch-toolkit-$version-source.tar.gz" \
  > "ict-branch-toolkit-$version-source.tar.gz.sha256"
```

Use an approved, version-pinned workflow to generate an SPDX JSON or CycloneDX
JSON SBOM from the same commit. Record the generator and version in the release
evidence. Inspect the archive and SBOM, then calculate their final checksums.
For pull requests and `main`, the `container-security` job in
`.github/workflows/security.yml` builds both application images, scans
actionable high and critical vulnerabilities, and uploads vulnerability-aware
CycloneDX JSON SBOMs with a `SHA256SUMS` manifest. The Trivy container reference
is pinned by version and immutable digest. Those workflow artifacts are
candidate evidence only; a maintainer must still inspect and approve them for
the exact candidate commit.

Recommended public artifact set:

| Artifact               | Required content                                                                                                               |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Source archive         | Only files tracked by the approved commit under one versioned directory.                                                       |
| SHA-256 manifest       | File names and digests for every downloadable artifact.                                                                        |
| SPDX or CycloneDX SBOM | Resolved backend, frontend, base-image, and build dependency inventory from the approved process.                              |
| Release notes          | Exact commit, verification links, limitations, human approvals, install/operate/recover links, and the non-production warning. |

Do not attach environment files, database dumps, recovery archives, raw logs,
test credentials, screenshots with sensitive content, signing keys, or private
infrastructure records.

## Publication and candidate retirement

Create the GitHub entry as a **Pre-release** only after the artifact digests and
approvals are final. Use this exact title pattern:

`ICT Branch Toolkit <version> — NON-PRODUCTION PROTOTYPE RELEASE CANDIDATE`

If a candidate fails evaluation:

1. record the defect and impact without exposing sensitive information;
2. withdraw deployment approval and restrict access when required;
3. preserve the tag, artifacts, checksums, and evidence for traceability;
4. fix the issue on a new commit;
5. repeat the complete checklist and publish the next RC number.

Do not replace artifacts under an existing tag or release entry. A later final
release requires its own approved process; successful RC evaluation does not by
itself establish production readiness.
