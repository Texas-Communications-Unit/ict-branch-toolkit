# Map provider deployment checklist

Complete this checklist before enabling an external basemap. Record the review
in the deployment change or pull request. A blank provider configuration keeps
the neutral map active.

## Approval and inventory

- [ ] Provider and intended environment are approved by a maintainer.
- [ ] Provider appears in `docs/governance/map-provider-inventory.json`.
- [ ] Current data, style, font, sprite, imagery, and boundary licenses have
      been reviewed.
- [ ] Current terms, attribution requirements, privacy policy, rate limits,
      caching rules, and service availability have been reviewed.
- [ ] Use is limited to synthetic data unless a separate operational privacy
      determination has been approved.

## Configuration and security

- [ ] Exactly one of `VITE_MAP_STYLE_URL` or `VITE_MAP_TILE_URL` is configured.
- [ ] All provider and metadata URLs use HTTPS.
- [ ] Provider ID, name, attribution, license, terms, privacy, issue-reporting,
      and operational-contact values are configured.
- [ ] Any browser token is organization-controlled, public-client scoped,
      origin restricted, quota limited, and contains no management authority.
- [ ] No secret, API administration key, credential, private server address, or
      operational connection information is committed.
- [ ] Required outbound HTTPS destinations are allowlisted; no new inbound
      service is opened merely to consume tiles.

## Public OpenStreetMap standard tiles

- [ ] The exact approved tile URL is used.
- [ ] Browser Referer behavior is not restricted.
- [ ] HTTP caching is not disabled or bypassed.
- [ ] No prefetch, bulk download, viewport automation, or offline package is
      enabled.
- [ ] Visible `© OpenStreetMap contributors` attribution links to the OSM
      copyright page.
- [ ] The installation publishes a Toolkit map support path and the OSM
      `Report a map issue` link.

## Verification and rollback

- [ ] An incomplete test configuration visibly falls back to the neutral map
      without issuing external tile requests.
- [ ] A provider outage falls back to the neutral map without blocking site,
      coordinate, or manual-ring work.
- [ ] Attribution and privacy disclosure remain visible at desktop and mobile
      widths.
- [ ] Official SVG, KML, GeoJSON, and CSV exports state that no external
      basemap data is included.
- [ ] The health endpoint, authentication, incident selection, site placement,
      markers, rings, and exports pass after the rebuild.
- [ ] Rollback is documented: clear all map-provider variables, rebuild only the
      frontend image, and redeploy the approved stack to restore the neutral
      map.
