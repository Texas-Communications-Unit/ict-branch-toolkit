# Security Policy

## Supported versions

Security fixes target the latest `main` commit. Older commits and independently modified installations do not receive backported fixes. Operators must review, approve, and deploy tested updates; merging a fix does not patch an installed server.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting feature for this repository. Do not open a public issue containing exploit details, credentials, protected communications data, personal information, or operational system information.

Include the affected commit or version, reproduction steps using synthetic data, likely impact, and any proposed mitigation. Maintainers will acknowledge a complete report when repository staffing permits; no service-level response time is promised during the prototype phase.

## Dependency and operational security

Maintainers follow the [security maintenance runbook](docs/operations/security-maintenance.md) for daily scans, dependency-update review, severity-based triage, deployment gates, and verification of the installed version. Automated checks do not authorize a merge, deployment, production test, or disclosure.

## Data handling

This public repository and its automated tests must contain only synthetic, public, or explicitly approved data. The prototype is not approved for real incident, controlled, protected, personal, credential, certificate, key, or private operational data.

