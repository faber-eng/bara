from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from adapters.samples import SampleLibrary
from config import Settings
from contracts import SampleItem, SampleKind

router = APIRouter(prefix="/api/samples")

MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".ogg": "audio/ogg",
    ".geojson": "application/geo+json",
}


def library(request: Request) -> SampleLibrary:
    settings: Settings = request.app.state.settings
    return SampleLibrary(settings.samples_dir)


@router.get("", response_model=list[SampleItem])
def list_samples(request: Request, kind: SampleKind | None = None) -> list[SampleItem]:
    items = [sample.item for sample in library(request).list()]
    if kind is None:
        return items
    return [item for item in items if item.kind == kind]


@router.get("/{sample_id}/file")
def sample_file(request: Request, sample_id: str) -> FileResponse:
    sample = library(request).find(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="sample not found")
    return FileResponse(sample.path, media_type=MEDIA_TYPES.get(sample.path.suffix))
