# ADR-0024: Azure federated deployment through managed Run Command

- Status: Proposed
- Date: 2026-11-03
- Decision owners: Maintainers

## Context

The Azure host restricts inbound SSH to approved administrator source addresses.
GitHub-hosted runner addresses vary. Broadening public SSH access or maintaining
large runner address lists is unsuitable for this deployment.

## Decision

Use GitHub OIDC and a dedicated Azure user-assigned managed identity, federated
only to this repository's protected `shared-test` environment. Keep the
environment restricted to `main` with required human review. Grant only VM read
and managed Run Command read/write/delete, assigned at the single VM resource scope.
Do not attach the deployment identity to the VM or grant network/IAM management.

The security workflow must pass before environment approval and identity token
issuance. Deliver the three deployment helpers from the exact scanned checkout
with checksums embedded in the command, rather than downloading a moving branch.
The Azure agent switches to the dedicated deployment account before processing
those helpers. Existing commit checks, consistent recovery sets, maintenance
locking, image scans and Compose health checks remain authoritative.

Manual dispatch defaults to a harmless connection verification that embeds no
actual deployment helpers. It has a separate concurrency group so it can verify
federation while a real deployment waits for human approval. Both operations
retain full security checks, main-only enforcement, and environment approval.

Use managed Run Command for long-running work. Check instance-view execution
state and zero exit code; resource provisioning success is insufficient. Keep
full logs private on the VM, exposing only status and commit identity to Actions.
Delete successfully completed command resources to avoid Azure's 25-command
limit; retain failures for Azure inspection. Never delete a running command
on runner timeout or cancellation. The script timeout is 50 minutes, the polling
budget is 55 minutes, and the Actions job budget is 60 minutes.

## Consequences

Public SSH stays restricted to administrators. No long-lived Azure client secret
or GitHub deployment SSH key is needed. Run Command can execute arbitrary code
as root on its target VM: VM scope limits the cloud blast radius, not the power
on that VM. Treat approved workflows and environment reviewers accordingly.
The application account's Docker access is also root-equivalent.

Azure agent health and Azure control-plane availability become deployment
dependencies. A runner disconnection can leave a command running; check Azure
execution status and application health before retrying. Preserve the host lock.
Full logs are deployment-account readable and require administrator access for
diagnosis. Failed command resources require operator retention review.

## Sources

- [Azure OIDC authentication](https://learn.microsoft.com/en-us/azure/developer/github/connect-from-azure-openid-connect)
- [Managed Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command-managed)
- [Azure Compute permissions](https://learn.microsoft.com/en-us/azure/role-based-access-control/permissions/compute)
