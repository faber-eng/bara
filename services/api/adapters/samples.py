import logging
from dataclasses import dataclass
from pathlib import Path

from contracts import SampleItem
from domain.samples import Catalog, build_catalog, parse_credits

logger = logging.getLogger(__name__)

CREDITS_FILE = "CREDITS.md"
IGNORED_FILES = frozenset({CREDITS_FILE, ".gitkeep"})


@dataclass(frozen=True)
class Sample:
    item: SampleItem
    path: Path


class SampleLibrary:
    def __init__(self, directory: Path):
        self._directory = directory

    def list(self) -> list[Sample]:
        catalog = self._catalog()
        for message in catalog.skipped:
            logger.warning("sample skipped: %s", message)
        return [
            Sample(item, self._directory / file)
            for item, file in sorted(
                catalog.entries.values(), key=lambda entry: entry[0].id
            )
        ]

    def find(self, sample_id: str) -> Sample | None:
        for sample in self.list():
            if sample.item.id == sample_id:
                return sample
        return None

    def _catalog(self) -> Catalog:
        return build_catalog(self._rows(), self._present())

    def _rows(self):
        try:
            text = (self._directory / CREDITS_FILE).read_text()
        except OSError:
            return []
        return parse_credits(text)

    def _present(self) -> set[str]:
        if not self._directory.is_dir():
            return set()
        return {
            path.relative_to(self._directory).as_posix()
            for path in self._directory.rglob("*")
            if path.is_file() and path.name not in IGNORED_FILES
        }
