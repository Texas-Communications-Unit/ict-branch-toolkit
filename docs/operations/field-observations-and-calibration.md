# Field observations and incident-local calibration

Issue #19 adds synthetic-only field-evidence and calibration workflows. This guide does not
authorize collection of real observations, use of operational coordinates, or approval of a
calibrated preset.

## Human gates

Before collecting any non-synthetic observation, record:

1. the incident authority permitting collection;
2. the security/privacy classification and approved users;
3. whether observer identity, time, coordinates, equipment details, signal measurements, and
   notes may be retained;
4. the approved location precision or redaction rule;
5. consent or other collection authority when a person or device can be identified;
6. retention, legal-hold, backup, export, disclosure, and destruction requirements; and
7. a qualified RF reviewer for observation quality, method assumptions, exclusions, and any
   calibrated recommendation.

Real observations must not be committed to the public repository, test fixtures, screenshots,
GitHub comments, Actions artifacts, or support bundles.

## Safe default

`ICT_APPROVED_CALIBRATION_METHODS=[]` prevents calibration-set approval. Draft synthetic
comparison remains available so the interface and evidence contract can be evaluated.

The only included algorithm is:

```text
observation-envelope-v1-provisional
```

After security/privacy, incident-authority, and qualified RF review of the exact method, an
installation can allow approval with:

```text
ICT_APPROVED_CALIBRATION_METHODS=["observation-envelope-v1-provisional"]
```

That setting does not authorize real collection and does not promote a recommendation to an
organization default.

## Observation workflow

1. Select the incident and distinct approved infrastructure and subscriber RF input snapshots.
2. Optionally select an approved coverage estimate or directional analysis using those exact
   inputs.
3. Classify the evidence as good, marginal, or failed communications.
4. Identify it as measured, operator judgment, imported, or modeled evidence.
5. Record the bounded time window, collection/source fields, environment, measurements, quality
   flags, and source revision.
6. Choose location handling deliberately:
   - **Exact** retains WGS 84 coordinates and declared precision.
   - **Generalized** rounds coordinates to the declared grid before persistence.
   - **Redacted** discards coordinates before persistence.
7. Submit the immutable observation.
8. An authorized reviewer records an append-only approval or exclusion reason.
9. Correct a record by creating a superseding observation. Never attempt to rewrite the original.

Imported records require a source-record identifier. Modeled observations require an approved
coverage or directional result. Archived, cross-incident, mismatched, or unapproved sources are
rejected.

## Calibration workflow

1. Select currently approved, non-superseded observations.
2. Name the calibration set and identify the exact baseline preset/version.
3. Review the minimum sample count and measured-to-predicted ratio bounds.
4. Create the next immutable version.
5. Review:
   - selected and usable counts;
   - classification distribution;
   - every missing-data or outlier exclusion;
   - the median distance multiplier;
   - before/after mean absolute error and percentage error;
   - algorithm, parameters, observation digest, result digest, and warning text; and
   - the explicit `incident_local`, `not_promoted` recommendation state.
6. Approve only after the configured human gate passes and the captured observation/review
   evidence is still current.

A changed review decision or superseding correction invalidates approval of an older draft. Create
a new calibration-set version from the current evidence.

## Privacy, retention, and export

- Treat exact/generalized locations, timestamps, observer/source text, notes, RF inputs,
  measurements, and source identifiers as the highest classification inherited from the
  incident or source.
- Prefer controlled identifiers over names. Do not place contact information, credentials,
  protected channels, private server details, or unrelated narrative in observer/source or notes.
- Generalization is not anonymization. Repeated locations, times, paths, or measurements may still
  identify a site, person, device, or operational capability.
- Observation records, reviews, and calibration sets are retained and immutable in this
  prototype. The installation owner must define retention and lawful destruction before real use.
- The current workflow has no observation or calibration export. Do not add one without a
  classified-field allowlist, authorization, redaction, digest, audit, and human transmission
  review.
- Database backups inherit the records' classification and retention requirements.

## Misuse and data-quality risks

- Good/marginal/failed labels are context-dependent operator evidence, not universal RF facts.
- Distance pairs can reflect route choice, obstruction, interference, equipment state, weather,
  user behavior, and measurement error rather than a propagation-model defect.
- The median bounded ratio is an explainable prototype, not a statistical validation study.
- Excluding an outlier may hide a real failure mode. Review every exclusion and quality flag.
- A lower before/after error on the selected observations does not establish generalization to
  another incident, band, site, subscriber, environment, or time.
- A calibrated recommendation never provides spectrum authorization, coordination approval, or a
  coverage guarantee.

## Verification

For an approved synthetic evaluation, confirm:

- generalized coordinates differ from the submitted exact coordinates;
- redacted records retain no coordinate or precision;
- correction creates `supersedes` and does not alter the original;
- approval/exclusion creates another review record;
- cross-incident and mismatched sources fail;
- missing distance pairs and out-of-bound ratios appear as exclusions;
- a set below the minimum sample count remains `insufficient_data`;
- result digests reproduce for identical canonical inputs;
- approval fails when the method is not allowlisted or review evidence changed; and
- no audit detail contains coordinates, notes, observer/source text, or measurement values.
