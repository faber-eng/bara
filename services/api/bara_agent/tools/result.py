from collections.abc import Mapping

from contracts import GeoPoint, RankingComponents

ToolResult = dict[str, object]


def tool_error(message: str) -> ToolResult:
    return {"error": message}


def count_label(count: int, singular: str, plural: str) -> str:
    if count == 1:
        return f"1 {singular}"
    return f"{count} {plural}"


def entries(result: Mapping[str, object], key: str) -> list[Mapping[str, object]]:
    value = result.get(key)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def score(value: float) -> float:
    return round(value, 1)


def radar_db(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def components_entry(components: RankingComponents) -> ToolResult:
    return {
        "s1_anom_db": radar_db(components.s1_anom_db),
        "rain_30d_mm": round(components.rain_30d_mm),
        "rain_deficit_pct": round(components.rain_deficit_pct, 2),
        "canal_dist_m": round(components.canal_dist_m),
        "peat_class": components.peat_class,
    }


def point_entry(point: GeoPoint) -> ToolResult:
    return {"lat": round(point.lat, 5), "lon": round(point.lon, 5)}
