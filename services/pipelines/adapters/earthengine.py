import ee
import google.auth

from ee_lib import grid
from ee_lib.config import DataConfig, RegionConfig

EE_SCOPES = (
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
)
PAGE_SIZE = 1000


def initialize(project: str) -> None:
    credentials, _ = google.auth.default(scopes=list(EE_SCOPES))
    ee.Initialize(credentials=credentials, project=project)


def compute_features(collection: ee.FeatureCollection) -> list[dict]:
    features: list[dict] = []
    token: str | None = None
    while True:
        params: dict[str, object] = {"expression": collection, "pageSize": PAGE_SIZE}
        if token is not None:
            params["pageToken"] = token
        page = ee.data.computeFeatures(params)
        features.extend(page.get("features", []))
        token = page.get("nextPageToken")
        if not token:
            return features


class EarthEngineSource:
    def __init__(self, data: DataConfig):
        self._data = data

    def peat_cells(self, region: RegionConfig, aoi: dict) -> list[dict]:
        return compute_features(grid.peat_cells(aoi, region, self._data))
