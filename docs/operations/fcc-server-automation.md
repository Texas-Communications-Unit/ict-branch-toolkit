# Server-native FCC synchronization

Routine FCC updates run on the Ubuntu server, using systemd and ordinary Python,
Docker, Bash, and Git commands. They do not call ChatGPT, an OpenAI API, or an AI
agent. No ChatGPT token allowance is required to schedule, supervise, verify, or
report these jobs. Existing VM, storage, network, and optional mail usage still
apply; no additional cloud service is provisioned.

## Operation

`toolkit-fcc-sync.timer` starts the job on Mondays at 10:30 UTC, with up to two
minutes of jitter: 04:30 CST / 05:30 CDT. This leaves an hour after the daily
backup window. Missed runs do not catch up unexpectedly when the VM starts.

The controller runs ASR, ULS commercial, and ULS private sequentially. It executes
the helper from the currently deployed clean, reviewed `main` release; it never
pulls, merges, or deploys application code. A deployed release may remain behind
repository `main` while a later release awaits deployment approval. The helper
still receives and independently checks the exact selected deployed commit.
Application deployment approvals remain unchanged. Only the redundant GitHub
FCC **schedule** is removed; its protected manual recovery workflow remains.

Each dataset retains the existing backup, HTTPS/archive checks, maintenance lock,
transactional publication, private temporary storage, timeout, and success marker.
After success, the controller requires one current batch and equality between
the database digest, host success marker, and actual downloaded archive digest.
It also checks application health. Partial `Staged` progress is never reported
as a committed dataset.

The controller checks the actual import process, not Gunicorn, and lowers its
address-space limit to the smaller of 4 GiB or half the available host/cgroup
memory. It also lowers only that process's CPU priority. The PID, process start
time, dataset, archive basename, and private operation directory must match.
PID reuse or an ambiguous process is refused. Memory limits can make a valid but
oversized import fail safely; they are not permission to raise archive limits or
silently resize the VM. Dataset execution remains bounded at 165 minutes and the
whole systemd job at twelve hours. Imports are not retried in an uncontrolled loop.

## Status and manual operation

The deployment account's private FCC automation state directory contains
`weekly-last.json`, `bootstrap-last.json`, and mode-0600 per-dataset logs. JSON
status includes timestamps, the deployed commit, aggregate progress, resource
observations, verified dataset digests/counts, and a final success/failure state.
It contains no credentials or incident records. Do not publish raw helper logs.

```sh
systemctl list-timers toolkit-fcc-sync.timer
systemctl show toolkit-fcc-sync.service -p Result -p ExecMainStatus
sudo journalctl -u toolkit-fcc-sync.service -n 40 --no-pager
sudo systemctl start --no-block toolkit-fcc-sync.service
```

A successful oneshot service normally returns to `inactive`; inspect `Result`,
`ExecMainStatus`, and the timestamped status file rather than treating `inactive`
as failure. Stopping a job is an operator action: confirm that its bounded
container import has stopped before retrying or removing temporary files.

## Installation and recovery

Install `scripts/fcc-server-automation.py` as root-owned mode 0755 at
`/usr/local/lib/ict-toolkit-fcc-sync.py`. Render the `.in` unit templates under
`systemd/` with the approved deployment account, group, application path, and data
mount. Install the timer unchanged. Keep a root-owned mode-0640 configuration at
`/etc/ict-toolkit-fcc.json`, readable only by root and the deployment group:

```json
{
  "app_dir": "/home/DEPLOY_USER/apps/ict-branch-toolkit",
  "env_file": "/home/DEPLOY_USER/.config/ict-branch-toolkit/deployment.env",
  "state_dir": "/home/DEPLOY_USER/.cache/ict-branch-toolkit/fcc-automation",
  "data_dir": "/home/DEPLOY_USER/data/ict-branch-toolkit/fcc",
  "maintenance_lock": "/home/DEPLOY_USER/.cache/ict-branch-toolkit/maintenance.lock",
  "public_base_url": "https://toolkit.tx-comu.org",
  "memory_limit_mib": 4096,
  "dataset_timeout_seconds": 9900,
  "maintenance_wait_seconds": 10800,
  "notifications_enabled": false,
  "notification_email": "operator@example.invalid"
}
```

No mail password or new GitHub token belongs in this file. When explicitly
authorized, failure notifications use the existing protected Compose SMTP
configuration, including encryption for authenticated SMTP. A separate
`toolkit-fcc-notify@.service` handles ordinary failures and interrupted systemd
jobs; successful runs send no email. A configuration test is available through
`--notify-test`. Notification errors stay in the journal, without printing SMTP
credentials or complete captured environment output.

Before activation, run the controller as the deployment account with `--check`,
verify rendered units with `systemd-analyze verify`, then run `systemctl
daemon-reload` and `systemctl enable --now toolkit-fcc-sync.timer`. Record installed
source-file checksums and the reviewed source commit privately. Updating the
root-owned controller is a separate reviewed operator installation, not something
the application account silently performs during data synchronization. Docker
group access remains root-equivalent on the VM; these are trusted operator jobs.

The optional bootstrap unit waits for an existing operation to stop, requires
its exact dataset's success message and matching database/marker/archive digests,
then imports the specified remaining dataset. A failed prerequisite stops the
handoff rather than blindly repeating it. Install this unit only for a specific
approved migration.

The optional temporary-memory cleanup unit is root-only and specific to a
recorded temporary resource. It waits for the maintenance lock and no active
import, verifies the exact allowed directory/name, root ownership, mode 0600,
single link, and 32 GiB size, and refuses persistent fstab configuration. It
disables only that swap file, confirms it is inactive, then unlinks it and updates
the private audit record. It never clears a directory or disables other swap.
Its boot condition also handles a reboot during the one-time migration. Routine
weekly jobs do not create swap files.

Rollback of scheduling is reversible: disable the systemd timer and restore the
GitHub schedule through a reviewed change. Do not run both schedulers. Preserve
application data and existing recovery sets throughout an installation rollback.
