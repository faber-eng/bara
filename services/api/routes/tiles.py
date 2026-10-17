import logging

from fastapi import APIRouter, HTTPException, Request

from adapters.earthengine import DryingTileSource, TileSourceError
from config import Settings
from contracts import TileLayer
from ee_lib.config import UnknownRegion, load_region
from ee_lib.weeks import FutureWeek, InvalidWeek, local_today, resolve_week, week_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tiles")


@router.get("/drying", response_model=TileLayer)
def drying_tiles(request: Request, region: str, week: str | None = None) -> TileLayer:
    settings: Settings = request.app.state.settings
    tiles: DryingTileSource = request.app.state.tiles
    now = request.app.state.utcnow()
    try:
        config = load_region(settings.config_dir, region)
    except UnknownRegion as error:
        raise HTTPException(
            status_code=404, detail=f"region {region!r} has no drying layer"
        ) from error
    try:
        week_start = resolve_week(week, now, config.zone)
    except (InvalidWeek, FutureWeek) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    label = week_label(week_start)
    try:
        url = tiles.drying_url_template(
            config, week_start, local_today(now, config.zone)
        )
    except TileSourceError as error:
        logger.error(
            "drying tiles failed",
            extra={"fields": {"region": region, "week": label, "error": str(error)}},
        )
        raise HTTPException(
            status_code=502, detail="Earth Engine could not build the drying tiles"
        ) from error
    return TileLayer(layer="drying", region=region, week=label, url_template=url)
