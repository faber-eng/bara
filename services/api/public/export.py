import csv
import io

from contracts import PublicCell

LICENSE = "CC BY-NC-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"
CREDITS = (
    "Peat mask: Global Peatland Map 2.0, Greifswald Mire Centre (CC BY-NC-SA 4.0)",
    "Radar: contains modified Copernicus Sentinel-1 data",
    "Rainfall: CHIRPS, Climate Hazards Center, UC Santa Barbara",
    "Canals: OpenStreetMap contributors (ODbL)",
)
CSV_COLUMNS = (
    "cell_id",
    "lat",
    "lon",
    "drying_score",
    "rank",
    "rank_change",
    "s1_anom_db",
    "rain_30d_mm",
    "rain_deficit_pct",
    "canal_dist_m",
    "peat_class",
)


def csv_row(cell: PublicCell) -> list[object]:
    components = cell.components
    return [
        cell.cell_id,
        cell.centroid.lat,
        cell.centroid.lon,
        cell.drying_score,
        cell.rank,
        "" if cell.rank_change is None else cell.rank_change,
        "" if components.s1_anom_db is None else components.s1_anom_db,
        components.rain_30d_mm,
        components.rain_deficit_pct,
        components.canal_dist_m,
        components.peat_class,
    ]


def csv_export(region: str, week: str, cells: list[PublicCell]) -> str:
    out = io.StringIO()
    out.write(f"# region: {region} week: {week}\n")
    out.write(f"# license: {LICENSE} {LICENSE_URL}\n")
    for credit in CREDITS:
        out.write(f"# credit: {credit}\n")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for cell in cells:
        writer.writerow(csv_row(cell))
    return out.getvalue()


def geojson_feature(cell: PublicCell, week: str) -> dict[str, object]:
    components = cell.components
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [cell.centroid.lon, cell.centroid.lat],
        },
        "properties": {
            "cell_id": cell.cell_id,
            "week": week,
            "drying_score": cell.drying_score,
            "rank": cell.rank,
            "rank_change": cell.rank_change,
            "s1_anom_db": components.s1_anom_db,
            "rain_30d_mm": components.rain_30d_mm,
            "rain_deficit_pct": components.rain_deficit_pct,
            "canal_dist_m": components.canal_dist_m,
            "peat_class": components.peat_class,
            "license": LICENSE,
        },
    }


def geojson_export(
    region: str, week: str, cells: list[PublicCell]
) -> dict[str, object]:
    return {
        "type": "FeatureCollection",
        "region": region,
        "week": week,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "credits": list(CREDITS),
        "features": [geojson_feature(cell, week) for cell in cells],
    }
