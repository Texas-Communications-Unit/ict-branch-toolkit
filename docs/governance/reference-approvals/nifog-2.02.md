# NIFOG 2.02 reference import approval

## Decision

**Approved for the ICT Branch Toolkit shared test environment on July 23, 2026.**

- Reviewing maintainer and communications reviewer: Eric M. Gildersleeve
- Role: Project Administrator
- Decision: Import the public NIFOG 2.02 channel tables as the first operational
  reference-library release.
- Scope: Public reference data only. This decision does not authorize operation
  on any frequency or talkgroup and does not waive licensing, eligibility,
  coordination, or usage conditions in the source document.

## Authoritative source

- Publisher: Cybersecurity and Infrastructure Security Agency (CISA)
- Document: National Interoperability Field Operations Guide, Version 2.02
- Cover date: January 2025
- Retrieved: July 23, 2026
- URL:
  `https://www.cisa.gov/sites/default/files/2024-12/NIFOG%202.02_508%20FINAL%20VERSION%2012%2003%202024.pdf`
- PDF SHA-256:
  `45c2f5d94861b3ed1b80f7ce5962a160fdd56092211586bdee711b68ca3d3142`

The importer rejects a PDF with a different checksum or page count. A future
NIFOG release requires a new review and approval record.

## Transformation and validation

The deterministic extractor reads the conventional-channel tables on printed
pages 28–59 and the SAR command-plan table on printed page 63. It preserves
channel identifiers, names, uses, RX/TX frequencies, bandwidth, mode,
squelch/NAC values, emission designators, eligibility, authorization and
restriction text, source section, and printed source page. Conventional
channels and trunked talkgroups remain separate resource types.

Expected and reviewed output:

- 230 conventional-channel records
- 32 deployable-system talkgroup records
- Source PDF: 192 pages
- Visual comparison samples: low-band mutual aid, 700 MHz nationwide
  interoperability, 700 MHz low-power, and deployable trunked-system tables
- Representative structured-record checks: LLAW1, VTAC17, IR 1, LE 2, MED-9,
  7CALL50, 7-US-01, DEPLOY-A, 8CALL90, VHF Marine Ch. 17, and deployable
  talkgroups

The bundled JSON is generated from the checksum-pinned PDF and is reviewed in
Git. Import remains atomic, additive, audited, and idempotent at startup.
