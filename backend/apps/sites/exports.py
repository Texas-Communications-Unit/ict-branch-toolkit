import csv
import html
import io
import json
import math
from xml.etree import ElementTree

from .services import approved_site_records

DISCLAIMER = (
    "Planning decision support only; not frequency coordination approval, "
    "spectrum authorization, or a guarantee of coverage."
)
BASEMAP_PROVENANCE = (
    "No external basemap data is included; this export contains only approved "
    "site, assignment, coordinate, and manual-ring records."
)
RING_COLORS = {
    "operational": "#2d7d46",
    "fringe": "#c17b16",
    "coordination": "#8d3b72",
}


def geojson_export(revision) -> bytes:
    features = []
    for record in approved_site_records(revision):
        properties = dict(record)
        properties["planning_limitation"] = DISCLAIMER
        features.append(
            {
                "type": "Feature",
                "id": record["site_id"],
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(record["longitude"]), float(record["latitude"])],
                },
                "properties": properties,
            }
        )
    payload = {
        "type": "FeatureCollection",
        "name": f"ICS-205 revision {revision.number} approved sites",
        "basemap_provenance": BASEMAP_PROVENANCE,
        "features": features,
    }
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode()


def csv_export(revision) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "site_id",
            "site_name",
            "latitude_wgs84",
            "longitude_wgs84",
            "ring_type",
            "radius_m",
            "assignments",
            "source_identity",
            "source_retrieved_at",
            "planning_limitation",
            "basemap_provenance",
        ]
    )
    for record in approved_site_records(revision):
        rings = record["rings"] or [{"type": "", "radius_m": "", "label": ""}]
        for ring in rings:
            writer.writerow(
                [
                    record["site_id"],
                    record["name"],
                    record["latitude"],
                    record["longitude"],
                    ring["type"],
                    ring["radius_m"],
                    " | ".join(record["assignments"]),
                    record["source_identity"],
                    record["source_retrieved_at"] or "",
                    DISCLAIMER,
                    BASEMAP_PROVENANCE,
                ]
            )
    return output.getvalue().encode("utf-8")


def kml_export(revision) -> bytes:
    namespace = "http://www.opengis.net/kml/2.2"
    ElementTree.register_namespace("", namespace)
    root = ElementTree.Element(f"{{{namespace}}}kml")
    document = ElementTree.SubElement(root, f"{{{namespace}}}Document")
    ElementTree.SubElement(
        document, f"{{{namespace}}}name"
    ).text = f"ICS-205 revision {revision.number} approved sites"
    ElementTree.SubElement(
        document, f"{{{namespace}}}description"
    ).text = f"{DISCLAIMER}\n{BASEMAP_PROVENANCE}"
    for record in approved_site_records(revision):
        placemark = ElementTree.SubElement(document, f"{{{namespace}}}Placemark")
        ElementTree.SubElement(placemark, f"{{{namespace}}}name").text = record["name"]
        ElementTree.SubElement(placemark, f"{{{namespace}}}description").text = "\n".join(
            record["assignments"]
        )
        point = ElementTree.SubElement(placemark, f"{{{namespace}}}Point")
        ElementTree.SubElement(
            point, f"{{{namespace}}}coordinates"
        ).text = f"{record['longitude']},{record['latitude']},0"
        for ring in record["rings"]:
            ring_placemark = ElementTree.SubElement(document, f"{{{namespace}}}Placemark")
            ElementTree.SubElement(ring_placemark, f"{{{namespace}}}name").text = (
                ring["label"] or f"{record['name']} — {ring['type']}"
            )
            polygon = ElementTree.SubElement(ring_placemark, f"{{{namespace}}}Polygon")
            boundary = ElementTree.SubElement(polygon, f"{{{namespace}}}outerBoundaryIs")
            linear_ring = ElementTree.SubElement(boundary, f"{{{namespace}}}LinearRing")
            coordinates = []
            latitude = float(record["latitude"])
            longitude = float(record["longitude"])
            for step in range(65):
                angle = math.radians(step * 360 / 64)
                north_m = math.cos(angle) * ring["radius_m"]
                east_m = math.sin(angle) * ring["radius_m"]
                ring_latitude = latitude + north_m / 111_320
                ring_longitude = longitude + east_m / (
                    111_320 * max(math.cos(math.radians(latitude)), 0.01)
                )
                coordinates.append(f"{ring_longitude:.7f},{ring_latitude:.7f},0")
            ElementTree.SubElement(linear_ring, f"{{{namespace}}}coordinates").text = " ".join(
                coordinates
            )
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def svg_export(revision) -> bytes:
    records = approved_site_records(revision)
    width, height, padding = 960, 640, 80
    if records:
        latitudes = [float(item["latitude"]) for item in records]
        longitudes = [float(item["longitude"]) for item in records]
        center_latitude = sum(latitudes) / len(latitudes)
        meters_per_lon = 111_320 * max(math.cos(math.radians(center_latitude)), 0.01)
        x_values = [longitude * meters_per_lon for longitude in longitudes]
        y_values = [latitude * 111_320 for latitude in latitudes]
        ring_extent = max(
            [ring["radius_m"] for item in records for ring in item["rings"]] or [1_000]
        )
        min_x, max_x = min(x_values) - ring_extent, max(x_values) + ring_extent
        min_y, max_y = min(y_values) - ring_extent, max(y_values) + ring_extent
        scale = min(
            (width - 2 * padding) / max(max_x - min_x, 1),
            (height - 2 * padding - 70) / max(max_y - min_y, 1),
        )
    else:
        x_values = y_values = []
        min_x = min_y = 0
        scale = 1

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">ICS-205 revision {revision.number} approved site map</title>',
        f'<desc id="desc">{html.escape(DISCLAIMER)} {html.escape(BASEMAP_PROVENANCE)}</desc>',
        '<rect width="100%" height="100%" fill="#f7fafb"/>',
        '<text x="40" y="38" font-family="sans-serif" font-size="22" font-weight="700" '
        'fill="#173743">ICT Branch Toolkit — Approved Radio Sites</text>',
        f'<text x="40" y="61" font-family="sans-serif" font-size="13" fill="#4d626b">'
        f"ICS-205 revision {revision.number}</text>",
    ]
    for index, record in enumerate(records):
        x = padding + (x_values[index] - min_x) * scale
        y = height - padding - (y_values[index] - min_y) * scale
        for ring in sorted(record["rings"], key=lambda item: item["radius_m"], reverse=True):
            radius = max(ring["radius_m"] * scale, 2)
            color = RING_COLORS[ring["type"]]
            lines.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{color}" '
                f'fill-opacity="0.08" stroke="{color}" stroke-width="2"/>'
            )
        lines.extend(
            [
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="#b5452b" stroke="white" '
                'stroke-width="2"/>',
                f'<text x="{x + 10:.2f}" y="{y - 9:.2f}" font-family="sans-serif" '
                f'font-size="13" font-weight="700" fill="#173743">'
                f"{html.escape(record['name'])}</text>",
                f'<text x="{x + 10:.2f}" y="{y + 9:.2f}" font-family="monospace" '
                f'font-size="10" fill="#4d626b">{record["latitude"]}, '
                f"{record['longitude']}</text>",
            ]
        )
    lines.extend(
        [
            f'<text x="40" y="{height - 24}" font-family="sans-serif" font-size="11" '
            f'fill="#5c6d75">{html.escape(DISCLAIMER)}</text>',
            f'<text x="40" y="{height - 8}" font-family="sans-serif" font-size="10" '
            f'fill="#5c6d75">{html.escape(BASEMAP_PROVENANCE)}</text>',
            "</svg>",
        ]
    )
    return "\n".join(lines).encode()


EXPORTERS = {
    "geojson": ("application/geo+json", "approved-sites.geojson", geojson_export),
    "csv": ("text/csv; charset=utf-8", "approved-sites.csv", csv_export),
    "kml": ("application/vnd.google-earth.kml+xml", "approved-sites.kml", kml_export),
    "map": ("image/svg+xml", "approved-site-map.svg", svg_export),
}
