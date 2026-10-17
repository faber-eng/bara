from contracts import (
    Bulletin,
    GeoPoint,
    PublicBulletin,
    PublicCell,
    PublicCells,
    RankedCell,
    RankingComponents,
)


def serialize_components(components: RankingComponents) -> RankingComponents:
    return RankingComponents(
        s1_anom_db=components.s1_anom_db,
        rain_30d_mm=components.rain_30d_mm,
        rain_deficit_pct=components.rain_deficit_pct,
        canal_dist_m=components.canal_dist_m,
        peat_class=components.peat_class,
    )


def serialize_cell(cell: RankedCell) -> PublicCell:
    return PublicCell(
        cell_id=cell.cell_id,
        centroid=GeoPoint(lat=cell.centroid.lat, lon=cell.centroid.lon),
        drying_score=cell.drying_score,
        rank=cell.rank,
        rank_change=cell.rank_change,
        components=serialize_components(cell.components),
    )


def serialize_cells(
    region: str, week: str, cells: list[RankedCell], limit: int
) -> PublicCells:
    return PublicCells(
        region=region,
        week=week,
        cells=[serialize_cell(cell) for cell in cells[:limit]],
    )


def serialize_bulletin(
    region: str, week: str, bulletin: Bulletin | None
) -> PublicBulletin:
    if bulletin is None:
        return PublicBulletin(
            region=region,
            week=week,
            text_id=None,
            text_en=None,
            cited=[],
            source=None,
            model=None,
            prompt_version=None,
            created_at=None,
        )
    return PublicBulletin(
        region=region,
        week=week,
        text_id=bulletin.text_id,
        text_en=bulletin.text_en,
        cited=list(bulletin.cited),
        source=bulletin.source,
        model=bulletin.model,
        prompt_version=bulletin.prompt_version,
        created_at=bulletin.created_at,
    )
