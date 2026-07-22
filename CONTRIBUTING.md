# Contributing

Thank you for helping improve ICT Branch Toolkit. The project is developed in public, but operationally sensitive material does not belong in the repository, issues, pull requests, screenshots, logs, or test artifacts.

## Before contributing

1. Open or locate an issue describing the change.
2. Create a focused branch from `main`.
3. Use only synthetic, public, or explicitly approved data.
4. Add or update tests and documentation.
5. Run `make check` or the equivalent commands in the README.

GitHub Issues are the project work queue. Human comments are recorded as task input and may be assessed by Codex under the controls in [`docs/governance/issue-lifecycle.md`](docs/governance/issue-lifecycle.md). External comments require maintainer review before paid AI execution or repository writes. Only trusted maintainers may use `/codex implement`, which creates a feature branch and draft pull request rather than changing `main`.

Do not submit real incident information, protected channel information, personal information, credentials, keys, certificates, database dumps, private endpoints, or operational connection details. If a security concern cannot be demonstrated safely with synthetic data, follow `SECURITY.md` instead of opening a public issue.

## Pull requests

Describe what changed, why, user or operator impact, assumptions, verification results, limitations, screenshots for UI work, and follow-up work. Keep dependency upgrades and broad formatting separate from feature changes unless they are inseparable.

All contributions are accepted under the repository's GNU AGPL v3 license.
