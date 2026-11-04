# Azure FCC synchronization and SSH retirement

The **Sync FCC reference data** workflow uses the existing VM-scoped GitHub
OIDC identity and Azure managed Run Command. It does not connect to public SSH
or require a long-lived Azure client secret. See the
[identity setup](azure-deployment-identity.md) for permissions and the protected
`shared-test` environment. These permissions remain root-equivalent on the
selected VM; give them only to trusted reviewed workflows.

## Approval, schedule, and verification

The workflow accepts only current `main`, checks out that exact commit, and
refuses stale runs. The host helper independently requires the same deployed
commit and a clean checkout while holding the host maintenance lock. Deploy
the reviewed main commit before verifying or running its FCC workflow.

Scheduled runs are Mondays at **10:30 UTC (04:30 CST / 05:30 CDT)**. This moves
the former 09:00 UTC schedule past the 09:30 UTC application-backup window.
Schedule timing is a buffer; the maintenance lock still prevents overlap.
FCC operations and application deployments also share the Actions concurrency
group. A queued job does not replace or cancel a running operation.

Both scheduled and manual runs require the existing `shared-test` environment
approval. Scheduled synchronization therefore waits for a reviewer; it does
not silently bypass approval to run unattended. Keep environment deployment
branches restricted to `main` and keep the reviewer requirement enabled.

After merging and deploying the reviewed main commit:

1. Select **Sync FCC reference data → Run workflow → main → operation: verify**.
2. Approve its environment request. Verification checks the exact checkout,
   protected configuration readability, Compose configuration, and running
   services. It does not download FCC archives, take a backup, or import data.
3. Confirm Azure instance-view reports `Succeeded` with exit code zero. A
   provisioning-success response alone is insufficient.
4. Separately approve an `operation: sync` run for one dataset or `all`.
   Confirm the private log, successful import or unchanged-digest result, and
   application health. Do not run a capacity/load test as transport validation.

The synchronization helper retains its official FCC HTTPS archive URLs,
digest-based no-change detection, private retained files, validated database
backup, no-write archive-capacity probe, transactional reconciliation, and
post-success digest marker. A failed import must not advance that marker.
Archives are streamed through the configured backend account into its own
mode-0700 temporary directory, with mode-0600 files. `docker cp` would create
root-owned files that the hardened non-root backend cannot read. The transfer
does not grant capabilities, change the backend user, or make archives public.

## Execution limits and failure handling

The Actions job retains its **180-minute** budget. Guest work is bounded at
165 minutes, Azure execution at 170 minutes, and runner polling at 174 minutes,
leaving room for authentication and cleanup. These deliberately exceed the
shorter application-deployment budget. Large datasets can still exceed this
limit and fail; inspect the existing operation before retrying or changing it.

The guest derives an absolute import deadline with a two-minute cleanup
reserve. Archive probes and imports run under `timeout` **inside** the backend
container, with a 30-second kill grace. The import's database connections also
enable PostgreSQL client-disconnection checks so the server can abort work
when the timed-out client exits. These are scoped to that import process;
application-wide database settings are not changed.

The guest terminates its host process group on timeout and removes only its
own temporary helper directory. Full output remains in mode-0600
`~/.cache/ict-branch-toolkit/fcc-sync-logs/<run-id>-<attempt>.log`. Actions shows
only status/commit information. Never copy protected configuration or database
records into public logs or issue comments.

Provisioning failure, nonzero execution, missing execution status, API failure,
and timeout fail the operation. Failed or unresolved Azure command resources
are retained for diagnosis; successful commands are removed only after zero
exit status is proven. Cancelling an Actions runner does not prove the async
Azure operation stopped. Inspect its instance-view state, host lock, and
container import processes before retrying. Do not delete a live command to
clear the dashboard.

## Retired server-connected capacity workflow

The old **Characterize shared-test collaboration capacity** Actions workflow
is retired because its target is now the live application VM. It must not
reuse this production identity to launch load tests. Existing retained reports
and synthetic characterization evidence are preserved.

The manual staging helper, typed confirmation, cleanup, checksum validation,
and report validation remain available for an explicitly approved **isolated
synthetic test host**. They are described in
[performance-tested limits](performance-tested-limits.md#shared-test-collaboration-capacity-probe).
Retirement of the Actions entry point does not authorize running those tools
against operational records. No production capacity test is part of this change.

## Retire only the obsolete machine credential

Do this as a separately approved administrator action only after both the
replacement verification and an approved synchronization have succeeded:

1. Search all active workflows for `secrets.DEPLOY_HOST`, `DEPLOY_PORT`,
   `DEPLOY_KNOWN_HOSTS`, and `DEPLOY_SSH_KEY`; confirm there are no consumers.
   Review queued/failed old runs before credential cleanup.
2. Identify the obsolete machine public key by its verified fingerprint in the
   dedicated account's `authorized_keys`. Preserve every administrator key and
   keep a tested administrator SSH connection open. Never replace the whole
   file with a guessed key list.
3. Remove only that matching machine-key entry, then remove only the four
   unused repository secrets above. Keep protected `DEPLOY_USER` and all Azure
   environment secrets; they are still required.
4. Reconfirm administrator SSH, HTTPS/API health, the replacement schedule,
   environment controls, and Azure verification. Record owner and evidence
   privately, without posting key material or server identifiers.

If verification fails, leave the credential in place while correcting the
replacement. Do not reopen public SSH to GitHub runner address ranges or
weaken organization sign-in policies.

Sources: [Azure managed Run Command](https://learn.microsoft.com/en-us/azure/virtual-machines/linux/run-command-managed),
[PostgreSQL connection checks](https://www.postgresql.org/docs/17/runtime-config-connection.html).
