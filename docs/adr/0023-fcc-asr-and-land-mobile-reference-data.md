# ADR-0023: FCC ASR and land-mobile reference data

- Status: Accepted
- Date: 2026-08-21
- Decision owners: Maintainers

## Context

The Toolkit needs authoritative public reference data for antenna structures and
two-way radio licenses. Issue #83 originally assumed that this required FCC API
keys. The FCC instead publishes complete and daily public-access archives that
can be retrieved without an FCC account or application credential.

The operational requirement is intentionally narrower than all FCC licensing
data. It includes Antenna Structure Registration (ASR), licenses held by
governmental entities, and commercial two-way land-mobile radio. It excludes
broadcast and Amateur Radio licensing.

## Decision

Use the FCC's HTTPS public-access archives as the authoritative upstream source:

- ASR registrations: `r_tower.zip`, reconciled with the complete archive and
  updated from `r_tow_<day>.zip` daily transaction archives.
- ULS private land-mobile licenses: `l_LMpriv.zip`, updated from
  `l_lp_<day>.zip`.
- ULS commercial land-mobile licenses: `l_LMcomm.zip`, updated from
  `l_lc_<day>.zip`.

Do not request, store, or require an FCC API key for this integration. Do not
screen-scrape FCC search pages. Retrieve only from configured FCC HTTPS hosts,
apply bounded download and extraction limits, calculate a SHA-256 digest for
every source archive, and retain source URL, retrieval time, archive timestamp,
and parser version.

The first implementation imports the latest complete registration and license
archives, then applies daily transactions idempotently. A later complete import
is an authoritative reconciliation. Source rows are retained with their status;
only current records are presented by default. A status must never be inferred
from an absent daily row.

ULS selection is deterministic:

1. Within the two approved land-mobile archive families, retain licenses whose
   FCC applicant type identifies a governmental entity, regardless of the
   land-mobile radio-service code.
2. Retain non-government licenses only when the radio-service code is in the
   reviewed, versioned two-way land-mobile allowlist in the ingestion
   specification.
3. Reject or quarantine an unrecognized radio-service code instead of silently
   broadening the import.

ASR registration data and ULS licenses remain separate source record types.
Linking a license location to an ASR registration is allowed only when an FCC
identifier provides the relationship; proximity alone must not create an
authoritative link.

## Consequences

The integration has no expected FCC subscription or credential cost. Bulk files
are large, so imports require streaming, bounded temporary storage, atomic
replacement or upsert behavior, and off-peak scheduling. Weekly reconciliation
limits drift if a daily file is missed.

Public FCC records still require data minimization. The Toolkit retains only
fields needed for search, mapping, license review, provenance, and later
decision support. It must not present FCC data as frequency authorization,
coordination approval, tower availability, or permission to use a site.

This ADR authorizes the source and scope decision. It does not itself enable a
production download, database migration, scheduled task, deployment, or use of
the data in an incident plan. Those require implementation tests, operational
review, and a separate reviewed pull request.

## Alternatives considered

FCC search-page automation was rejected because it is brittle and unnecessary.
FCC API-key management was rejected because these public archives do not require
credentials. Importing all ULS services was rejected because broadcast,
Amateur, personal-radio, aviation, marine, and unrelated market-based services
are outside the stated requirement. A paid third-party data provider was
rejected because the FCC supplies the required source data directly.
