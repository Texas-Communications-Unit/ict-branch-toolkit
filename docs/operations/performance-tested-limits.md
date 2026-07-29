# Tested performance limits

## Status and interpretation

These limits apply to the **ICT Branch Toolkit P1.0 non-production
prototype**. They are deterministic regression envelopes for representative
read-heavy API workloads, not a production capacity rating, service-level
objective, or authorization to use operational data.

The tests intentionally use database-query budgets and uncompressed JSON byte
budgets instead of elapsed-time assertions. Query counts and response bytes are
repeatable across hardware classes; wall-clock thresholds in shared CI are too
sensitive to runner contention to be a reliable release gate.

## Published envelopes

`backend/tests/test_performance_limits.py` creates only synthetic records and
tests these authenticated list paths:

| Workload                   | Synthetic dataset and returned page                                                           | Database-query budget | JSON response budget |
| -------------------------- | --------------------------------------------------------------------------------------------- | --------------------: | -------------------: |
| Incident list              | 101 incident memberships; first 100 incidents, each with 2 operational periods                |                     6 |              128 KiB |
| Incident update with audit | 1 incident membership; status patch plus append-only audit event                              |                    12 |                8 KiB |
| Conventional-channel list  | 1,001 channels; oversized request is clamped to 1,000 results                                 |                     4 |              1.5 MiB |
| Radio-site list            | 101 sites; first 100 sites, each with 3 manual rings                                          |                     5 |              256 KiB |
| ICS-205 plan list          | 25 plans, 2 revisions per plan, 10 assignments and 1 two-assignment relationship per revision |                    10 |              512 KiB |

The query budgets cover request transaction control, pagination counts, object
retrieval, nested serialization, and—on the update workload—the material write
and audit append. They exclude the single token-authentication lookup so the
tests isolate endpoint data-access behavior. The response budgets cover the
uncompressed JSON body produced by the fixed synthetic fixtures; they do not
cap arbitrarily long text values or HTTP headers.

P3.3 adds two bounded plan-list queries: one resolves the requester's
incident-scoped role for restricted fields and one loads the incident's
sensitive-field rules. Request-scoped caching keeps those checks constant per
incident rather than per assignment. On July 28, 2026, the same synthetic plan
fixture measured 10 queries and 350,877 bytes with server-side field filtering.

The general API page size is 100. The channel-library endpoints default to 500
and accept `page_size` only up to 1,000. The tests verify the incident and site
default page boundary and the channel-library maximum. The plan test is a
representative 25-plan nested workload, not a claim that revisions or
assignments have a hard application-level maximum.

On July 27, 2026, the isolated suite passed locally with Python 3.12.10 and
SQLite. It measured 6 queries and 96,190 bytes for the incident list; 4 queries
and 1,283,120 bytes for channels; 5 queries and 148,638 bytes for sites; 8
queries and 374,577 bytes for plans; and 11 queries and 545 bytes for the
audited incident update. This is evidence for the published hardware-neutral
budgets, not a PostgreSQL/PostGIS or deployed-load result.

## Reproduce and measure

Run the isolated suite from `backend/`:

```sh
pytest --no-cov -q tests/test_performance_limits.py
```

To print one JSON measurement record per workload:

```sh
ICT_PERFORMANCE_REPORT=1 pytest --no-cov -q -s tests/test_performance_limits.py
```

PowerShell uses:

```powershell
$env:ICT_PERFORMANCE_REPORT = "1"
pytest --no-cov -q -s tests/test_performance_limits.py
Remove-Item Env:ICT_PERFORMANCE_REPORT
```

The normal backend CI job also runs this suite as part of `pytest` against
PostgreSQL/PostGIS. Local SQLite runs are useful for fast regression feedback;
the CI database path remains required before merge.

## Deliberate limitations and release gates

These tests do not measure concurrent users, sustained or write-heavy imports,
PDF or spatial-export generation, network latency, reverse-proxy behavior,
database growth over time, or deployment-specific CPU and memory use. The one
audited incident update is a regression envelope, not a sustained-write load
test. The tests do not establish a maximum incident count or a safe operational
user count.

Before any production claim or hosted use beyond the approved synthetic test
scope, maintainers must run a deployment-specific load test with synthetic
data, review database query plans and resource utilization, define acceptable
latency and concurrency targets, and complete the Issue #7 security and
operational human gates. Maintainer approval is still required for every merge
and deployment.

## Phase 2 validation workload

P2.6 adds focused deterministic integration coverage for one approved plan,
one HAAT/coverage/directional chain, three reviewed synthetic observations, one
calibration set, one validation bundle, controlled export, digest verification,
cancellation/retry, stale-review handling, and incident isolation.

The first implementation executes the validation result synchronously after an
explicit request. It does not publish a wall-clock capacity, concurrency limit,
queue throughput, or safe maximum observation count. General pagination and
authenticated throttling still apply. The interface reports durable staged
state, but mid-request cancellation and background-worker recovery are
explicitly unsupported.

The server rejects a bundle above 1,000 plan assignments or 1,000 calibration
observations and rejects verification uploads above 10 MiB. Those ceilings
bound accidental resource use; the current release-candidate fixture does not
validate performance at either ceiling.

Before expanding the tested synthetic scope, record observation/assignment
counts, result/export byte size, PostgreSQL query plans, CPU/memory, concurrent
requests, timeout behavior, and audit growth. Do not infer production capacity
from the three-observation release-candidate fixture.

## Terrain-analysis workload

P3.1 bounds one terrain profile to 200,000 meters and 1,001 samples by default.
Terrain history returns five records per page and permits an explicit page size
only up to ten so completed profile evidence cannot multiply into an unbounded
list response. The browser renders the full profile table only when its
disclosure is opened.
The focused synthetic regression evaluates the maximum default profile
(200-meter interval) and currently requires completion in under five seconds
on the local test runner. That elapsed-time assertion guards deterministic
algorithmic regression only; it is not a service-level objective, concurrent
capacity rating, or real-dataset/provider benchmark.

The same suite covers flat, ridge, valley, missing, dataset-boundary,
out-of-coverage, datum-offset, provider-failure, queued cancellation, retained
retry, incident isolation, and a lower configured sample limit. Synthetic
generation is network-free and does not measure provider latency, disk/cache
I/O, database/result growth under repeated work, or transformation-grid cost.

Before approving a real provider or raising either bound, record source and
result byte size, database growth, CPU/memory, transformation cost, provider
latency/timeouts/rate limits, concurrent requests, cancellation behavior, audit
growth, and recovery under failure. Use synthetic data for load testing. A
successful 1,001-sample fixture does not validate terrain accuracy or authorize
operational use.

## Online-collaboration workload

P3.3 bounds one recent-change response to 100 records by default and permits a
configured value only from 10 through 500. Presence expires after 75 seconds by
default and is configurable only from 30 through 300 seconds. These are response
and recovery bounds, not database-retention limits.

Deterministic SQLite tests cover two independent assignment edits, one
same-record conflict, idempotent replay, rejected mutation-ID reuse,
approved-revision rejection, presence expiry, active membership revocation,
restricted-field omission/redaction, and conflict resolution. They do not
establish a safe concurrent-user count, sustained mutation rate, audit-chain
throughput, PostgreSQL lock-wait target, or reverse-proxy timeout.

Before operational activation, run synthetic PostgreSQL tests for concurrent
edits to independent and shared targets, history growth, audit-chain contention,
worker saturation, abnormal disconnects, membership revocation, backup/restore,
and client retry storms. Record query plans, p50/p95/p99 latency, CPU, memory,
database growth, lock waits, error rate, and recovery time. The 20-second browser
poll and 75-second lease are initial coordination settings, not a service-level
objective.

## Planning-extension workload

P3.4 accepts only a declared JSON object below 16 KiB. The synthetic example
accepts one integer from 1 through 1,000 and runs against one approved ICS-205
revision. A handler result must match its declared schema and stay at or below
1 MiB. Extension and execution list responses use the standard 100-record
page. The focused SQLite regression holds the one-entry catalog to six queries
and the incident-scoped execution list to eight queries, including
authentication and authorization checks.

Two identical synthetic runs must produce identical canonical input and result
digests, and repeated downloads of one retained run must be byte-identical.
Failure-isolation coverage forces the optional handler to fail, verifies a
bounded retained failure/`503`, and then verifies health and incident-list
routes remain available.

These bounds validate the contract example, not arbitrary future tools. The
framework currently executes synchronously and publishes no duration,
concurrency, throughput, queue, CPU, or memory claim. Each future extension
must define its own input/output sizes, database/query budget, duration,
timeout, concurrency, job/cancellation/recovery behavior, and deployment load
evidence before enablement.
