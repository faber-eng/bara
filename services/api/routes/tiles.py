import logging
from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, HTTPException, Request

from adapters.earthengine import LayerNotReady, TileSource, TileSourceError
from config import Settings
from contracts import TileLayer, TileLayerKind
from ee_lib.config import RegionConfig, UnknownRegion, load_region
from ee_lib.weeks import FutureWeek, InvalidWeek, local_today, resolve_week, week_label

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tiles")

UrlBuilder = Callable[[TileSource, RegionConfig, date, date], str]


def serve_layer(
    request: Request,
    layer: TileLayerKind,
    region: str,
    week: str | None,
    build_url: UrlBuilder,
) -> TileLayer:
    settings: Settings = request.app.state.settings
    tiles: TileSource = request.app.state.tiles
    now = request.app.state.utcnow()
    try:
        config = load_region(settings.config_dir, region)
    except UnknownRegion as error:
        raise HTTPException(
            status_code=404, detail=f"region {region!r} has no {layer} layer"
        ) from error
    try:
        week_start = resolve_week(week, now, config.zone)
    except (InvalidWeek, FutureWeek) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    label = week_label(week_start)
    try:
        url = build_url(tiles, config, week_start, local_today(now, config.zone))
    except LayerNotReady as error:
        raise HTTPException(status_code=404, detail=f"not_ready: {error}") from error
    except TileSourceError as error:
        logger.error(
            f"{layer} tiles failed",
            extra={"fields": {"region": region, "week": label, "error": str(error)}},
        )
        raise HTTPException(
            status_code=502, detail=f"Earth Engine could not build the {layer} tiles"
        ) from error
    return TileLayer(layer=layer, region=region, week=label, url_template=url)


@router.get("/drying", response_model=TileLayer)
def drying_tiles(request: Request, region: str, week: str | None = None) -> TileLayer:
    return serve_layer(
        request,
        "drying",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.drying_url_template(
            config, week_start, today
        ),
    )


@router.get("/peat", response_model=TileLayer)
def peat_tiles(request: Request, region: str, week: str | None = None) -> TileLayer:
    return serve_layer(
        request,
        "peat",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.peat_url_template(config),
    )


@router.get("/burn_scars", response_model=TileLayer)
def burn_scar_tiles(
    request: Request, region: str, week: str | None = None
) -> TileLayer:
    return serve_layer(
        request,
        "burn_scars",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.burn_scars_url_template(
            config, week_start, today
        ),
    )


@router.get("/reignition", response_model=TileLayer)
def reignition_tiles(
    request: Request, region: str, week: str | None = None
) -> TileLayer:
    return serve_layer(
        request,
        "reignition",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.reignition_url_template(
            config, week_start, today
        ),
    )
