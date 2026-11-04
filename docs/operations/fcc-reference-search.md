# FCC reference search and capacity validation

Authenticated users with channel-library view permission can search the current imported FCC datasets at `/api/fcc-licenses/` and `/api/fcc-antenna-structures/`. The website exposes the same functions in the **FCC Reference** workspace. Searches are read-only and results include archive provenance.

## Dataset status

Expand **FCC dataset status and provenance** in the FCC Reference workspace for
read-only status cards for ASR, ULS private
land mobile, and ULS commercial land mobile. It shows the current local import's
archive retrieval/import timestamps, retrieval age, retained record counts, and
expandable archive/source/digest provenance. Missing imports and conflicting
current imports are explicit; future timestamps require review rather than
displaying a negative age. Missing count metadata is shown as unknown, not zero.

The `/api/fcc-dataset-status/` endpoint uses the existing `library.view` policy
and three bounded import-metadata queries. It does not scan the nationwide
reference tables, launch a synchronization, or return operator identities,
private paths, or workflow logs. Counts are the parser's retained archive counts,
not a new recount of records or a statement about all FCC licenses.

Retrieval age is not an FCC publication date, licensing-validity determination,
or proof of the last source check. Unchanged-archive checks do not create an
import batch, so their check time is currently unavailable in this dashboard.
The separate protected synchronization workflow remains the operator source for
those execution results. A status request failure leaves reference search usable.

The panel has automated keyboard, error/retry, narrow-reflow, and WCAG A/AA axe
checks. Those checks do not replace the human accessibility review in Issue #69.

## Map layer

The radio-site planning map uses
`/api/fcc-antenna-structures/map-features/` for the visible WGS 84 bounds and
zoom level. The endpoint groups structures into server-side grid clusters at
normal zoom levels and returns individual structures in close views. This
prevents a statewide request from silently displaying only the first page of
ASR records. Users can filter the visible layer by owner or identifier search,
FCC status code, and structure type. The same map symbols are presented as an
accessible list, so opening structure, license, frequency, and emission details
does not require pointer interaction.

Structure details link to the corresponding FCC ASR record and associated
licenses link to FCC ULS. These links are convenience references; the imported
archive digest and retrieval date remain the Toolkit's displayed provenance.

Before any production import, copy an official archive to a temporary server location and run the no-write capacity probe:

```console
python manage.py probe_fcc_archive_capacity /temporary/path/l_LMpriv.zip --dataset uls_private
```

The JSON output reports archive digest, compressed and expanded sizes, expansion ratio, member count, available disk space, and confirms zero database writes. This validates archive structure and storage headroom; it does not import or reconcile records. Production import remains a separately approved operation.

The **Sync FCC reference data** workflow runs each Monday at 10:30 UTC, after
the FCC creates complete files Sunday at 05:00 Eastern. It can also be started
manually for one dataset or all datasets. Both paths require protected-environment
approval and use Azure OIDC rather than SSH. Manual runs default to a no-import
verification; explicitly choose `sync` to apply data. See
[Azure FCC synchronization](azure-fcc-synchronization.md) for the verification,
timeout, schedule, and credential-retirement procedure. The workflow retains the current
archives in a mode-700 server directory and skips database work when a digest
is unchanged. For every changed archive it creates and validates a PostgreSQL
backup, runs the no-write capacity validation, and transactionally reconciles
the dataset. A digest marker is advanced only after a successful import.

The FCC complete files occasionally contain an unescaped pipe inside an entity
or contact name. The parser repairs only the validated `EN.dat` layouts where
the shifted FRN and one-character applicant code prove the extra delimiter's
location. Any other unexpected field shift fails closed instead of silently
misaligning license data.

FCC reference results are planning decision support. They do not authorize frequency use, transmission, coordination, or site access.
