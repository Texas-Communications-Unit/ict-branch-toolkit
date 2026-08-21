# FCC ASR and land-mobile reference-data ingestion specification

This specification implements the source and scope decision in
[ADR-0023](../adr/0023-fcc-asr-and-land-mobile-reference-data.md). It defines the
contract for a future importer; it does not activate an FCC connection.

## Authoritative sources

Use only the FCC public-access download host. Do not construct requests against
the interactive ASR or ULS search screens.

| Dataset | Complete archive | Daily archive pattern | Included upstream records |
| --- | --- | --- | --- |
| ASR registrations | [`r_tower.zip`](https://data.fcc.gov/download/pub/uls/complete/r_tower.zip) | `r_tow_<day>.zip` in the [daily directory](https://data.fcc.gov/download/pub/uls/daily/) | Registration records and their related entity, coordinate, condition, remark, and history rows |
| ULS private land mobile | [`l_LMpriv.zip`](https://data.fcc.gov/download/pub/uls/complete/l_LMpriv.zip) | `l_lp_<day>.zip` in the daily directory | Government/public-safety and Industrial/Business land-mobile licenses selected below |
| ULS commercial land mobile | [`l_LMcomm.zip`](https://data.fcc.gov/download/pub/uls/complete/l_LMcomm.zip) | `l_lc_<day>.zip` in the daily directory | Commercial two-way land-mobile licenses selected below |

The [FCC ULS Open Data description](https://opendata.fcc.gov/Wireless/FCC-Universal-Licensing-System-ULS-/x28i-i4z4)
identifies complete and daily transaction files as public access methods. The
[FCC public-access file guide](https://wireless.fcc.gov/uls/documentation/pa_intro24.pdf)
documents the pipe-delimited archive structure, complete-file cadence, and daily
transaction behavior.

### Explicit exclusions

Do not retrieve or import:

- ASR applications (`a_tower.zip`) or FAA determination archives
  (`d_tower.zip`) in the first implementation;
- ULS application archives (`a_*.zip`);
- land-mobile broadcast (`l_LMbcast.zip`);
- Amateur Radio (`l_amat.zip`);
- AM, FM, television, or public-inspection-file records;
- GMRS, ship, aircraft, coast, cellular, paging, microwave, market-based, or
  other ULS archive families.

These exclusions are archive boundaries, not deletion instructions. A future
scope change requires review and a new ADR or amendment.

## ULS selection rules

Read the ULS license header and licensee entity row before related records.
Include a license when either rule is true:

1. the FCC licensee entity applicant type is `G` (governmental entity) and the record came from
   one of the two approved land-mobile license archives; or
2. its radio-service code appears in the allowlist below.

The initial reviewed allowlist is:

| Purpose | Conventional | Trunked |
| --- | --- | --- |
| Public Safety Pool | `PW` | `YW` |
| Public Safety/Special Emergency, 800 MHz | `GP` | `YP` |
| Public Safety National Plan | `GF` | `YF` |
| Public Safety/Special Emergency and Public Safety, National | `GE` | `YE` |
| Public Safety 700 MHz | `SG` | `SY` |
| Industrial/Business Pool | `IG` | `YG` |
| Industrial/Business Pool - Commercial | `IK` | `YK` |
| Business, 800 MHz | `GB` | `YB` |
| Business, 900 MHz | `GU` | `YU` |
| Other Industrial/Land Transportation, 800 MHz | `GO` | `YO` |
| Other Industrial/Land Transportation, 900 MHz | `GI` | `YI` |
| Combined Business and Industrial/Land Transportation | `GJ` | `YJ` |
| Specialized Mobile Radio, 800 MHz | `GX` | `YX` |
| Specialized Mobile Radio, 900 MHz | `GR` | `YS` |
| Site-specific Specialized Mobile Radio, 800 MHz | `GM` | `YM` |
| Site-specific Specialized Mobile Radio, 900 MHz | `GL` | `YL` |

Also include these public-safety land-mobile services when present:

- `QM`: non-nationwide public safety/mutual aid at 220 MHz;
- `IQ`: intelligent transportation service (public safety);
- `SL`: state 700 MHz public-safety license; and
- `PA`: 4940-4990 MHz public-safety service.

Also include the FCC's auctioned commercial SMR codes `YC`, `YD`, and `YH` when
they occur in an approved land-mobile archive. These services do not form a
simple conventional/trunked pair in the FCC code list.

This is a source-selection list, not an authorization list. The importer must
store the matched rule and allowlist version. It must fail validation when an
archive contains a previously unseen radio-service code that would otherwise
appear eligible. Maintainers and a qualified communications reviewer decide
whether to add that code.

## Minimum retained fields

Preserve source record keys needed to join the FCC tables and reproduce the
import. Normalize only after retaining the raw source value.

### ASR registration

- FCC registration number and source unique identifier;
- registration status and status date;
- owner/entity name and public business contact fields needed for identification;
- structure type;
- latitude and longitude, datum/source value, and parsed WGS 84 point;
- ground elevation, structure height, and overall height in source units and
  canonical meters;
- FAA study/reference identifiers when present;
- FCC painting and lighting specifications;
- issue, construction, dismantlement, and expiration dates when present;
- FCC conditions and remarks; and
- source archive metadata, row type, digest, and parser version.

### ULS license

- FCC unique system identifier, call sign, FRN, radio-service code, applicant
  type, and source-selection rule;
- license status, grant date, effective date, expiration date, cancellation
  date, and last action date when present;
- licensee/entity name and public business address needed for identification;
- location number, location type/class, address, county, state, latitude,
  longitude, source datum, and parsed WGS 84 point;
- antenna number, structure type, antenna height, support height, and azimuth
  when present;
- assigned frequency, frequency location/antenna relationship, station class,
  transmit power, effective radiated power, and number of units when present;
- emission designator and associated frequency relationship;
- FCC conditions and status/history records needed to interpret the license;
  and
- source archive metadata, source row keys, digest, and parser version.

Store frequencies as integer hertz, coordinates as WGS 84, and heights and
distances canonically in meters. Preserve original text and units beside parsed
values when precision or interpretation could otherwise be lost.

## Import and update behavior

### Initial complete-archive command

The first implementation accepts a complete archive already downloaded from the
approved FCC host. It performs validation only unless `--apply` is supplied. The
archive basename must exactly match the selected dataset.

```sh
cd backend
python manage.py import_fcc_archive /staging/r_tower.zip \
  --dataset asr \
  --source-url https://data.fcc.gov/download/pub/uls/complete/r_tower.zip
```

After reviewing the digest and record counts, an Administrator may apply that
same unchanged archive:

```sh
python manage.py import_fcc_archive /staging/r_tower.zip \
  --dataset asr \
  --source-url https://data.fcc.gov/download/pub/uls/complete/r_tower.zip \
  --apply --username <administrator>
```

Use `uls_private` with `l_LMpriv.zip` and `uls_commercial` with
`l_LMcomm.zip`. Reapplying the same dataset and SHA-256 digest is an audited
no-op. This command does not download archives or process daily transactions;
those remain follow-up work after complete-file imports are operationally
validated.

1. Run an initial complete ASR and ULS import in a staging table or equivalent
   isolated import area.
2. Verify archive type, expected member names, decompressed-size limits, record
   counts, join integrity, coordinate ranges, frequency ranges, and allowlist
   coverage before publishing a version.
3. Publish atomically; a partial archive must never replace the last successful
   dataset.
4. Apply each daily archive once, keyed by source family, archive date, digest,
   and row identifier. Reprocessing the same archive must be a no-op.
5. Run a complete reconciliation weekly after the FCC complete files are
   published. A complete reconciliation supersedes derived current state but
   does not erase source provenance or import audit history.
6. If a daily archive is missed, malformed, unexpectedly empty, or out of
   sequence, retain the last successful dataset, raise an operational warning,
   and recover through the next complete reconciliation.

Default user searches show current registrations and licenses. Historical,
expired, cancelled, terminated, or dismantled records remain distinguishable
when retained for change processing and provenance.

## Security, privacy, and cost controls

- No FCC username, FRN login, API key, browser session, or paid provider is
  required.
- Permit HTTPS downloads only from the approved FCC host and reject redirects
  to unapproved hosts.
- Stream downloads to bounded temporary storage; reject path traversal,
  duplicate member names, encrypted archives, unsupported compression, and
  configured compressed/decompressed size or record-count limits.
- Calculate and retain SHA-256 before parsing. Never execute archive contents.
- Apply connection, read, and total-job timeouts with bounded retries and
  backoff. A failed refresh must not make the last valid dataset unavailable.
- Minimize public contact data. Do not import private attachments or fields that
  are not necessary for the stated operational purpose.
- Schedule large complete downloads off peak. Daily archives reduce bandwidth
  and processing cost; the weekly complete files provide drift recovery.

FCC data is public reference data, not operational truth. Every screen or export
that uses it must identify the FCC source date and state that the result does not
grant spectrum authority, frequency coordination, site access, tower loading
approval, or permission to transmit.

## Acceptance tests for the future importer

The implementation pull request must include synthetic fixtures shaped like the
FCC records; it must not commit a complete FCC archive. Tests must prove:

- only the three approved source families are accepted;
- broadcast and Amateur archive names are rejected;
- governmental-entity and allowlist selection rules are deterministic;
- unknown codes fail closed with a reviewable error;
- related ASR and ULS rows join only through FCC source keys;
- frequencies and spatial/unit fields normalize without losing source values;
- duplicate daily imports are idempotent and out-of-order input is detected;
- malformed and oversized ZIP input cannot escape or exhaust configured limits;
- a failed refresh preserves the last successful published dataset; and
- provenance and source-date notices survive API serialization and export.
