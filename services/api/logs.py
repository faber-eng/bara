import json
import logging
import sys

LIBRARY_NOTICES = {
    "google_genai.types": "Warning: there are non-text parts in the response",
    "google_auth_httplib2": "httplib2 transport does not support per-request timeout",
}


class LibraryNoticeFilter(logging.Filter):
    def __init__(self, prefix: str):
        super().__init__()
        self.prefix = prefix

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith(self.prefix)


def drop_library_notices() -> None:
    for name, prefix in LIBRARY_NOTICES.items():
        library = logging.getLogger(name)
        kept = [f for f in library.filters if not isinstance(f, LibraryNoticeFilter)]
        library.filters = [*kept, LibraryNoticeFilter(prefix)]


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    drop_library_notices()


def log_extra(event: str, **fields: object) -> dict[str, dict[str, object]]:
    return {"fields": {"event": event, **fields}}
