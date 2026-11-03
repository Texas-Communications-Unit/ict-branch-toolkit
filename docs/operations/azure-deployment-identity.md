# Azure deployment identity

The [deployment decision](../adr/0024-azure-federated-deployment.md) replaces
public runner-to-VM SSH with GitHub OIDC and managed Run Command. The application,
reverse proxy, database, data disk, and administrator SSH rule remain unchanged.

## Administrator setup

Use Azure CLI and GitHub CLI signed in through organization-approved methods. Keep Entra
Security Defaults and Conditional Access enabled. The setup operator needs
permission to create a user-assigned identity and federated credential, create
a custom role definition in the VM resource group, and assign that role at the
VM. Subscription ownership or appropriately delegated permissions are required;
ordinary VM access is insufficient. Review the script before running it.

From an approved repository checkout in Linux or Azure Cloud Shell Bash with
both CLIs installed and authenticated:

```bash
az account set --subscription '<approved-subscription-id>'
bash scripts/configure-azure-deployment.sh \
  '<resource-group>' '<vm-name>' "$HOME/toolkit-azure-deployment.private.json"
```

The script creates a dedicated user-assigned identity, never attaches it to the
VM, and configures this exact trust:

- Issuer: `https://token.actions.githubusercontent.com`
- Audience: `api://AzureADTokenExchange`
- Subject: GitHub's effective `sub_claim_prefix` followed by `:environment:shared-test`.

The setup script reads `GET /repos/{owner}/{repo}/actions/oidc/customization/sub`
through GitHub CLI before making Azure changes. With immutable subjects enabled,
the prefix has the form `repo:OWNER@OWNER-ID/REPOSITORY@REPOSITORY-ID`; the older
name-only form does not match it. Do not disable immutable subjects or add a
wildcard to work around an authentication failure. The script rejects custom
subject templates, missing effective prefixes, and unexpected repository names.
Review a custom template separately before using this setup procedure.

For `AADSTS700213`, compare the Azure credential's subject, issuer, and audience
with the **Federated token details** in the failed Azure Login step. Update only
the Azure subject to match the exact GitHub-issued value; retain the protected
environment suffix and VM-scoped permissions. See Microsoft's
[immutable-subject migration guidance](https://learn.microsoft.com/en-us/entra/workload-id/workload-identities-github-immutable-subjects).

The custom role has exactly:

- `Microsoft.Compute/virtualMachines/read`
- `Microsoft.Compute/virtualMachines/runCommands/read`
- `Microsoft.Compute/virtualMachines/runCommands/write`
- `Microsoft.Compute/virtualMachines/runCommands/delete`

Its assignment is at the single VM resource ID, not the group or subscription.
The group is only the role definition's allowed assignment boundary. It cannot
change network rules, Azure role assignments, or other VMs. Run Command itself
is root-equivalent on this VM; only trusted reviewed workflows may receive it.
No client secret, SSH private key, or application credential is generated.

Import the five output fields as `shared-test` environment secrets. Keep
`DEPLOY_USER` set to the existing dedicated account. Do not paste output into
issues, commits, public Actions logs, or chat. The local setup output is mode
0600 and must remain private. Keep environment approval enabled and deployment
branch policy restricted to `main`; the environment subject alone does not
distinguish branches or workflows.

## Verification before the first deployment

1. Confirm the VM's Azure Linux agent is healthy and supports managed Run Command.
2. Inspect the identity's federated credential, exact VM role assignment, and
   lack of additional group/subscription permissions.
3. In Actions, select **Deploy to Server → Run workflow → main → verify**.
   Approve this verification run's `shared-test` environment request after its
   Security checks pass. It authenticates with `Azure/login` and executes only
   an account-identity check. It cannot invoke the actual deployment helpers.
   Verification uses a separate concurrency group so a deployment awaiting
   approval cannot prevent this harmless check. Leave that deployment unapproved.
4. Confirm an unapproved branch cannot use the environment. Confirm the Security
   gate succeeds for the reviewed candidate and obtain normal deployment approval.
5. After deployment, check Azure instance-view `executionState=Succeeded` and
   `exitCode=0`, the server checkout SHA, Compose health, HTTPS API health, login,
   and operator-viewed map. Do not call provisioning success deployment success.

Pushes to `main` still queue deployment after full checks and approval. Manual
runs default to `verify`; explicitly choose `deploy` for a manual application
upgrade. Both modes require the protected environment and exact-current-main
check. Verification performs no backups, migrations, builds, or Docker pruning.

The runner sends the three helpers from its scanned checkout as a compressed
payload with SHA-256 checksums. The agent switches to `DEPLOY_USER` before
unpacking or executing them. The deployment script still independently fetches
and requires current `origin/main`, takes a matched recovery set, scans actual
candidate images, and waits for health checks. It refuses inadequate disk space;
this transport does not automatically prune Docker objects.

Full deployment output remains in mode-0600
`~/.cache/ict-branch-toolkit/deployment-logs/<run-id>-<attempt>.log` under the
deployment account. Actions exposes only status and commit identity, not build
logs or protected application settings. Azure command metadata contains public
deployment helper code; it contains no application secrets. Retain command
resources for failed executions and review retention periodically. Successfully
completed resources are deleted only after verifying a zero guest exit code,
avoiding Azure's 25-command limit. Cleanup errors warn without misreporting an
already successful application deployment as failed.

## Failure, cancellation, and rollback

A failed or nonzero guest execution fails Actions. Provisioning failure, missing
execution status, API failure, and timeout fail closed. Inspect the private host
log and Azure Activity Log without copying secrets to Actions or issues.

Cancellation or lost connectivity can leave the managed command running. Do not
delete its resource or dispatch another deployment until an administrator checks
its execution state and service health. The host maintenance lock also prevents
overlapping deployment and FCC writes. The guest timeout is 50 minutes; the
runner waits up to 55 minutes within a 60-minute job. A forced timeout may require
manual application resumption or restore; follow the
[recovery runbook](backup-restore-and-rollback.md).

Disable this deployment identity by deleting its VM role assignment or federated
credential. This does not stop the running application or remove administrator
SSH access. Reverting the workflow requires a reviewed PR and a working approved
transport; reverting to public-runner SSH alone restores the original timeout.
