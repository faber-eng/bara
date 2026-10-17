from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import get_args

from contracts import SampleItem, SampleKind

KINDS: frozenset[str] = frozenset(get_args(SampleKind))
CREDITS_COLUMNS = 5


@dataclass(frozen=True)
class CreditRow:
    file: str
    label: str
    author: str
    licence: str


@dataclass(frozen=True)
class Catalog:
    entries: dict[str, tuple[SampleItem, str]]
    skipped: list[str]


def parse_credits(text: str) -> list[CreditRow]:
    rows = []
    for line in text.splitlines():
        row = parse_row(line)
        if row is not None:
            rows.append(row)
    return rows


def parse_row(line: str) -> CreditRow | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    if len(cells) != CREDITS_COLUMNS:
        return None
    file, label, author, licence, _ = cells
    if file == "file" or set(file) <= {"-", ":"}:
        return None
    return CreditRow(file, label, author, licence)


def kind_of(file: str) -> str | None:
    parts = PurePosixPath(file).parts
    if len(parts) != 2 or ".." in parts:
        return None
    if parts[0] not in KINDS:
        return None
    return parts[0]


def sample_id(file: str) -> str:
    return PurePosixPath(file).stem


def to_item(row: CreditRow, kind: str) -> SampleItem:
    identifier = sample_id(row.file)
    return SampleItem(
        id=identifier,
        kind=kind,
        label=row.label,
        credit=f"{row.author}, {row.licence}",
        url=f"/api/samples/{identifier}/file",
    )


def build_catalog(rows: list[CreditRow], present: set[str]) -> Catalog:
    entries: dict[str, tuple[SampleItem, str]] = {}
    skipped: list[str] = []
    listed = {row.file for row in rows}
    skipped.extend(f"no credits row: {file}" for file in sorted(present - listed))
    for row in rows:
        reason = skip_reason(row, present, entries)
        if reason is not None:
            skipped.append(f"{reason}: {row.file}")
            continue
        entries[sample_id(row.file)] = (to_item(row, kind_of(row.file)), row.file)
    return Catalog(entries, skipped)


def skip_reason(
    row: CreditRow, present: set[str], entries: dict[str, tuple[SampleItem, str]]
) -> str | None:
    if kind_of(row.file) is None:
        return "unknown kind or path"
    if row.file not in present:
        return "no file"
    if sample_id(row.file) in entries:
        return "duplicate id"
    return None
