# Open mapping compliance

## Decision boundary

The ICT Branch Toolkit defaults to a network-free neutral MapLibre style. An
external basemap is optional and fails closed unless its endpoint and governance
metadata are complete. Geocoding remains separately controlled and disabled by
default.

The provider configuration supports either one HTTPS MapLibre style URL or one
HTTPS raster tile template. Configuring both is invalid. Any external
configuration also requires provider identity, visible attribution, data
license, terms, privacy, issue-reporting, and operational-contact metadata.
Invalid or incomplete configuration renders the neutral map and sends no map
requests.

## Limited OpenStreetMap testing

As reviewed on 2026-07-23, the OpenStreetMap Foundation permits normal
interactive browser viewing of its standard raster tiles when the application:

- uses `https://tile.openstreetmap.org/{z}/{x}/{y}.png`;
- displays visible OpenStreetMap attribution linked to its copyright page;
- preserves the normal browser Referer header and HTTP caching behavior;
- does not prefetch, bulk-download, scrape, or create offline packages;
- treats the service as best-effort with no service-level agreement; and
- does not send personal, confidential, protected, or operationally sensitive
  information to the service.

The Toolkit does not add a proxy, crawler, pre-seeding process, download control,
or background tile request. The browser requests only tiles required for the
operator's current viewport. Public OSM tiles are therefore a limited
synthetic-data test option, not an operational or production dependency.

Authoritative policy references:

- [OSMF tile usage policy](https://operations.osmfoundation.org/policies/tiles/)
- [OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)
- [OSM copyright and ODbL information](https://www.openstreetmap.org/copyright)
- [OSMF privacy policy](https://osmfoundation.org/wiki/Privacy_Policy)

Provider policies can change. Recheck them immediately before every production
approval.

## Operator privacy notice

When an external basemap is enabled, the interface identifies the provider and
warns that viewport requests disclose the geographic area being viewed. Do not
use a public map or geocoder for protected incident locations, confidential
addresses, personal information, or other operationally sensitive content
without an approved privacy and operational-security determination.

Browser-delivered map credentials, if a future provider requires them, must be
public client tokens restricted by allowed origin, product, and quota. Never put
provider administration credentials or unrestricted secrets in a `VITE_`
variable because Vite embeds those values in browser JavaScript.

## Attribution and official exports

External interactive maps show the configured attribution, license, terms,
privacy, map-issue, and Toolkit-support links adjacent to the map.

Current SVG, KML, GeoJSON, and CSV exports do not capture or redistribute the
interactive basemap. They are deterministic renderings of approved Toolkit
site, assignment, coordinate, and manual-ring records. Each export explicitly
states that it contains no external basemap data. A future export that includes
OSM-derived or other third-party map content must freeze the provider, source,
style, license, attribution, and retrieval/version metadata with the approved
revision before it can be enabled.

## QGIS and offline boundaries

This change does not distribute QGIS, expose PostGIS to QGIS, create an OGC
service, or authorize offline tile packages. Independently installed QGIS
Desktop remains operationally separate. Any QGIS Server, database connection,
or offline map package requires a separate design, least-privilege access
review, license review, and maintainer approval.

## Software notices

MapLibre GL JS is retained as a pinned dependency. Its complete license and
bundled third-party notices are copied from the installed package into
`/third-party/maplibre-gl-LICENSE.txt` in every production frontend build.
