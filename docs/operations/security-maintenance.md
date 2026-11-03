# Security maintenance

## Ownership and review

The repository administrator owns triage and assigns a named maintainer to each actionable finding. Check GitHub's Security tab, failed scheduled workflows, and Dependabot pull requests each working day. Enable personal notification delivery for Dependabot and failed Actions runs; repository settings cannot guarantee delivery to an individual. Private reports and exploitation details remain private.

Recommended operational targets, rather than a contractual response guarantee: triage critical or known-exploited findings immediately, other high findings within one working day, and other findings within five working days. Aim to mitigate critical/known-exploited findings within 24 hours and high findings within seven days. When a target cannot be met, document the affected deployment, exposure, temporary controls, owner, and next review date privately. Do not dismiss findings solely to make checks pass.

## Detection and proposed fixes

- GitHub dependency alerts and automatic security updates must be enabled. Secret scanning and push protection must be enabled. Check these settings monthly and after ownership or organization-policy changes.
- `.github/dependabot.yml` requests daily Python, JavaScript, Dockerfile, and Compose image update checks, and weekly Actions updates. Security update proposals remain separate from routine updates; no automatic merge is configured. Major updates require compatibility review.
- The Security workflow runs daily at 09:23 UTC, on pull requests, manually, and as the mandatory pre-deployment workflow. Pull-request scope avoids unrelated expensive scans; recurring and deployment runs scan the full application.
- Python audit blocks on all reported findings. JavaScript audit blocks on high/critical findings. Both audits run even if one fails. Review lower-severity and unfixable findings too; absence of a patch is not evidence of safety.
- Fresh backend, frontend, and production PostGIS images are built with `--pull`. Trivy produces vulnerability-aware CycloneDX SBOMs for all three images and blocks fixable high/critical findings. SBOMs are retained for 30 days, including failed scans. Review host Ubuntu/Apache/OpenSSH updates, Docker Engine, database configuration, and pinned scanning tools separately each month and immediately after a relevant advisory. Image scans do not patch an installed server or establish secure database configuration.
- CodeQL and Gitleaks provide code and secret checks. No scanner establishes absence of vulnerabilities. Never upload real data or protected deployment configuration as test evidence.

## Safe updates and deployment gate

1. Prepare a feature branch with exact dependency pins and the frontend lockfile when applicable. Check upstream release notes and supported runtime versions. Avoid unrelated upgrades.
2. Require `Security gate` on main pull requests. Relevant jobs include backend tests against disposable PostGIS, PDF/image/API regression tests, migration/schema checks, frontend lint/type/tests/build/browser checks, dependency audits, CodeQL, and image/secret scans. Failed, cancelled, or unavailable required checks are not approval.
3. Main pushes invoke the full reusable Security workflow inside `Deploy to Server`. Only its successful completion allows the deployment job to request protected `shared-test` environment approval. Manual dispatch from a non-main ref is skipped. The deployed SHA is the scanned SHA; a newer main commit causes refusal instead of silently promoting unscanned code.
4. A human reviews and merges, then approves the maintenance window. Preserve the matched database, attachments, environment recovery set and prior code identity. The server rebuilds all three images with fresh base images and without cached dependency layers. It scans those actual candidate images before container replacement; scan errors or fixable high/critical findings abort deployment. A preparation failure restores the previous checkout identity while original containers continue running. This requires outbound registry/advisory access and can extend build time. Keep users out throughout the upgrade and verification window; see [deployment recovery guidance](shared-test-deployment.md).
5. Verify the installed commit, container health, login, maps, synthetic PDF/image operations, and access to existing authorized records without copying their contents into public logs. Record the deployed SHA, image identifiers, scan/run links, backup reference, approver, and verification outcome in the private operator record.
6. A merge or passing candidate scan does not prove production is patched. Keep the finding open until installation and verification are confirmed. Roll back using the matched recovery set when an incompatible migration or data change requires it.

Daily scans rebuild the candidate from main, not the already-running image. Compare production image/version inventory with the last approved deployment after every update and during monthly review. Retain an encrypted off-host recovery copy and test restoration separately; security scanning does not provide backups.

## Exceptions and incident response

Never add a blanket advisory ignore, disable push protection, or bypass the deployment gate to clear a release. A justified false-positive or temporary risk acceptance requires a private record containing advisory ID, affected version and exposure, evidence, named owner/approver, expiry, and compensating controls. Any narrowly scoped scanner exception must link to that record without publishing sensitive details.

If a credential is exposed, revoke/rotate it first, assess access logs, and then remove the exposure. If exploitation is suspected, preserve evidence, restrict affected access, and follow the organization's incident process. Do not test an exploit against production without explicit approval.

## Initial remediation on 2026-11-03

The failed audit reported 68 advisory records across Django REST Framework 3.17.2, Pillow 12.3.0, and pypdf 6.16.1. The fix pins 3.18.3, 13.0.0, and 6.21.4 respectively. Advisory counts can differ between scanners and aliases and do not describe 68 separate proven exploitation paths. This record describes candidate remediation; deployment verification is a separate operational action.

Running the JavaScript audit independently also found vulnerable development dependencies that the earlier failed Python step had hidden. Vite and Vitest receive patch updates; the lockfile and reviewed brace-expansion, minimatch, and undici overrides receive fixes. Full lint, type, unit, build, and browser checks validate those toolchain changes. The Python container moves from 3.12.11 to the supported 3.12.16 security release; operating-system package upgrades alone cannot update the interpreter under `/usr/local`.

Scanning the upstream database image exposed fixable Alpine package findings and the old Go runtime compiled into `gosu`. `database/Dockerfile` upgrades Alpine packages and rebuilds pinned upstream gosu 1.20 with Go 1.27.3, preserving PostgreSQL 17/PostGIS 3.5, entrypoint, extensions, and volume format. Dependabot monitors its base/toolchain images; review the pinned gosu source commit monthly. The installed-stack/recovery workflow is now reusable and required by the Security gate for backend/container changes and every deployment, including clean initialization, backup/isolated restore, migration rollback/reapply, and audit-chain verification.

Production backend stages install GDAL/GEOS runtime libraries, while headers and GIS development tools remain in the development stage. The gosu build also pins the corrected `golang.org/x/sys` version 0.44.0. Review full SBOM findings rather than adding severity counts from unrelated vendors: CycloneDX can include several conflicting vendor ratings for one advisory. Vendor-unfixed or low-severity records remain visible in the reports and need documented applicability/mitigation review; a clean fixable-high/critical gate is not a zero-vulnerability certificate.

References: [Dependabot configuration](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference), [GitHub reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows), [Pillow release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html), and [Django REST framework release notes](https://www.django-rest-framework.org/community/release-notes/).
