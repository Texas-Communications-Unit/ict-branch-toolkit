# Spatial input and reference-source controls

Reviewed: July 23, 2026

## Coordinate behavior

The API accepts:

- Decimal degrees as `latitude, longitude`, including signed values.
- Degrees and decimal minutes (DDM) with hemisphere letters.
- Degrees, minutes, and seconds (DMS) with hemisphere letters.
- USNG/MGRS strings at supported grid precision.
- Map clicks and draggable pins, recorded as decimal WGS 84 coordinates.

Latitude is limited to -90 through 90 and longitude to -180 through 180. Minutes and seconds must be below 60. Ambiguous angular pairs without a comma are rejected. The parser returns normalized decimal, DDM, DMS, and USNG/MGRS representations, while the site retains the original entered text and input format.

## Address-provider boundary

`ICT_GEOCODER_PROVIDER` defaults to `apps.sites.geocoders.DisabledGeocoder`. Coordinate entry, map placement, rings, and exports remain fully usable when no address provider or network connection exists. A deterministic synthetic provider exists only for automated tests.

Before configuring a live provider, review its permitted use, privacy behavior, retention, attribution, availability, rate limits, and failure handling. Record provider identity and retrieval time for any selected result.

## FCC and FCCInfo evaluation

| Source | Role | P1.3 decision |
| --- | --- | --- |
| [FCC Antenna Structure Registration](https://www.fcc.gov/wireless/bureau-divisions/competition-infrastructure-policy-division/antenna-structure-registration) | Authoritative federal registration system for structures that require registration; it is not a complete inventory of every radio site. | Preferred source for persisted ASR facts after a separate import design and approval. |
| [FCC Universal Licensing System open data](https://opendata.fcc.gov/Wireless/FCC-Universal-Licensing-System-ULS-/x28i-i4z4) | Authoritative FCC licensing and downloadable license/application data. | Preferred source for persisted licensing and location facts after a separate import design and approval. |
| [FCCInfo search](https://www.fccinfo.com/) | Third-party operator convenience interface. | Evaluated but not placed in the application UI pending review of terms, privacy, attribution, reliability, and appropriate disclaimer language. |
| [FCCInfo Google Earth/KMZ](https://www.fccinfo.com/fccinfo_google_earth.php) | Third-party overlay that states its broadcast, microwave, and tower data are automatically kept up to date. It also depends on Google Earth for the documented workflow. | No adapter or ingestion enabled. A future adapter must expose provider identity, retrieval time, refresh status, stale/failure state, and authoritative FCC fallback. |

FCCInfo requires acceptance of its terms and links to its own disclaimer and privacy statement. Convenience or freshness claims do not make the service authoritative. The toolkit must never silently refresh an approved plan, and a live overlay must never overwrite an approval-time site snapshot.

## Current limitations

- No live geocoder, FCC, FCCInfo, or Google Earth integration is enabled.
- No real operational site selections are included in fixtures or tests.
- The SVG map has no street, parcel, imagery, or terrain basemap.
- Manual rings are not RF coverage calculations, interference contours, coordination approvals, or guarantees.
