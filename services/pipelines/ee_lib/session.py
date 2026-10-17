from datetime import UTC, date, datetime

import ee
import google.auth

from ee_lib import drying
from ee_lib.config import DataConfig

EE_SCOPES = (
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
)


def initialize(project: str) -> None:
    credentials, _ = google.auth.default(scopes=list(EE_SCOPES))
    ee.Initialize(credentials=credentials, project=project)


def latest_chirps_day(data: DataConfig, before: date) -> date | None:
    millis = drying.chirps_last_millis(data, before).getInfo()
    if millis is None:
        return None
    return datetime.fromtimestamp(millis / 1000, UTC).date()
