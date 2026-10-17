import logging
from collections.abc import Callable
from datetime import date

from fastapi import APIRouter, HTTPException, Request, Response

from adapters.earthengine import LayerNotReady, TileSource, TileSourceError
from config import Settings
from contracts import TileLayer, TileLayerKind
from ee_lib.config import RegionConfig, UnknownRegion, load_region
from ee_lib.weeks import FutureWeek, InvalidWeek, local_today, resolve_week, week_label
from tile_cache import TileUrlCache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tiles")

TILE_CACHE_CONTROL = "public, max-age=300"

UrlBuilder = Callable[[TileSource, RegionConfig, date, date], str]


def serve_layer(
    request: Request,
    response: Response,
    layer: TileLayerKind,
    region: str,
    week: str | None,
    build_url: UrlBuilder,
) -> TileLayer:
    settings: Settings = request.app.state.settings
    tiles: TileSource = request.app.state.tiles
    cache: TileUrlCache = request.app.state.tile_cache
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
        url = cache.get_or_build(
            (layer, region, label),
            lambda: build_url(tiles, config, week_start, local_today(now, config.zone)),
        )
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
    response.headers["Cache-Control"] = TILE_CACHE_CONTROL
    return TileLayer(layer=layer, region=region, week=label, url_template=url)


@router.get("/drying", response_model=TileLayer)
def drying_tiles(
    request: Request, response: Response, region: str, week: str | None = None
) -> TileLayer:
    return serve_layer(
        request,
        response,
        "drying",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.drying_url_template(
            config, week_start, today
        ),
    )


@router.get("/peat", response_model=TileLayer)
def peat_tiles(
    request: Request, response: Response, region: str, week: str | None = None
) -> TileLayer:
    return serve_layer(
        request,
        response,
        "peat",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.peat_url_template(config),
    )


@router.get("/burn_scars", response_model=TileLayer)
def burn_scar_tiles(
    request: Request, response: Response, region: str, week: str | None = None
) -> TileLayer:
    return serve_layer(
        request,
        response,
        "burn_scars",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.burn_scars_url_template(
            config, week_start, today
        ),
    )


@router.get("/reignition", response_model=TileLayer)
def reignition_tiles(
    request: Request, response: Response, region: str, week: str | None = None
) -> TileLayer:
    return serve_layer(
        request,
        response,
        "reignition",
        region,
        week,
        lambda tiles, config, week_start, today: tiles.reignition_url_template(
            config, week_start, today
        ),
    )
