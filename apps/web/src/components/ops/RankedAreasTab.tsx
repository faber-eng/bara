import { useQuery } from "@tanstack/react-query";
import {
  type KeyboardEvent,
  type MouseEvent,
  memo,
  type SyntheticEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { isNotFoundError } from "../../lib/api/client";
import { allCellsQuery, casesQuery, rankingsQuery } from "../../lib/api/queries";
import type { Case, RankedCell, Rankings } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import { rowSelection } from "../../lib/ops/cellSelection";
import { regionById } from "../../lib/ops/region";
import { formatFixed, formatNumber } from "../../lib/public/format";
import { ScoreBadge, StatusBadge } from "../detail/badges";
import { rankChangeShort, scoreBand } from "../detail/facts";
import { QueryState } from "./QueryState";
import {
  brokenDamCells,
  filterCounts,
  mainReason,
  matchesFilter,
  openCaseByCell,
  RANKED_FILTERS,
  type RankedFilter,
  type RowReason,
} from "./rankedRows";

const PERCENT = 100;
const ROW_SELECTOR = "button.mv-row";

function reasonText(reason: RowReason, copy: DetailCopy, language: CopyLanguage): string {
  switch (reason.kind) {
    case "brokenDam":
      return copy.ranked.brokenDam;
    case "radar":
      return copy.ranked.radar(formatFixed(reason.value, 1, language));
    case "rain":
      return copy.ranked.rain(formatNumber(Math.round(reason.value * PERCENT), language));
    case "canal":
      return copy.ranked.canal(formatNumber(Math.round(reason.value), language));
    default:
      return unhandledReason(reason);
  }
}

function unhandledReason(reason: never): never {
  throw new Error(`unhandled ranked reason: ${JSON.stringify(reason)}`);
}

function moveFocus(event: KeyboardEvent<HTMLOListElement>) {
  const step = { ArrowDown: 1, ArrowUp: -1 }[event.key];
  if (step === undefined) return;
  const rows = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>(ROW_SELECTOR));
  const current = rows.findIndex((row) => row === document.activeElement);
  const next = rows[Math.min(rows.length - 1, Math.max(0, current + step))];
  if (next === undefined) return;
  event.preventDefault();
  next.focus();
}

type RowView = {
  cell: RankedCell;
  line: string;
  band: string;
  openCase: Case | undefined;
};

function rowViews(
  cells: readonly RankedCell[],
  openCases: ReadonlyMap<string, Case>,
  brokenDams: ReadonlySet<string>,
  copy: DetailCopy,
  language: CopyLanguage,
): RowView[] {
  const views: RowView[] = [];
  for (const cell of cells) {
    const reason = mainReason(cell, brokenDams);
    const change = rankChangeShort(cell.rank_change, copy);
    views.push({
      cell,
      line: reason === null ? change : `${reasonText(reason, copy, language)} · ${change}`,
      band: scoreBand(cell.drying_score, copy),
      openCase: openCases.get(cell.cell_id),
    });
  }
  return views;
}

function cellIdOf(target: EventTarget): string | undefined {
  if (!(target instanceof Element)) return undefined;
  return target.closest<HTMLElement>("[data-cell-id]")?.dataset.cellId;
}

type RowProps = { view: RowView; selected: boolean; copy: DetailCopy };

const RankedRow = memo(function RankedRow({ view, selected, copy }: RowProps) {
  const rowRef = useRef<HTMLLIElement>(null);
  const { cell, line, band, openCase } = view;

  useEffect(() => {
    if (selected) rowRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  return (
    <li ref={rowRef}>
      <button
        type="button"
        className="ops-cell-button mv-row mv-row-ranked"
        aria-pressed={selected}
        data-cell-id={cell.cell_id}
      >
        <span className="mv-row-rank num" aria-hidden="true">
          {cell.rank}
        </span>
        <span className="mv-row-main">
          <strong className="mv-row-title">{cell.cell_id}</strong>
          <span className="mv-row-line">
            <span className="mv-row-meta">{line}</span>
            {openCase !== undefined && <StatusBadge status={openCase.status} copy={copy} />}
          </span>
        </span>
        <span className="mv-row-score">
          <ScoreBadge score={cell.drying_score} />
          <span className="mv-row-band">{band}</span>
        </span>
      </button>
    </li>
  );
});

type FilterProps = {
  value: RankedFilter;
  counts: Record<RankedFilter, number>;
  copy: DetailCopy;
  onChange: (filter: RankedFilter) => void;
};

function FilterSwitch({ value, counts, copy, onChange }: FilterProps) {
  return (
    <fieldset className="segmented mv-filter">
      <legend className="visually-hidden">{copy.ranked.filterLabel}</legend>
      {RANKED_FILTERS.map((filter) => (
        <button
          key={filter}
          type="button"
          aria-pressed={filter === value}
          onClick={() => onChange(filter)}
        >
          {copy.ranked.filters[filter]} <span className="num">{counts[filter]}</span>
        </button>
      ))}
    </fieldset>
  );
}

type ListProps = {
  rankings: Rankings;
  region: string;
  selectedCellId: string | undefined;
  onSelect: (cellId: string) => void;
  onHighlight: (cellId: string | undefined) => void;
};

function RankedList({ rankings, region, selectedCellId, onSelect, onHighlight }: ListProps) {
  const language = useCopyLanguage();
  const copy = detailCopy(language);
  const casework = regionById(region).casework;
  const cases = useQuery({ ...casesQuery(region), enabled: casework });
  const allCells = useQuery(allCellsQuery(region));
  const [filter, setFilter] = useState<RankedFilter>("all");
  const caseData = casework ? cases.data : undefined;
  const openCases = useMemo(() => openCaseByCell(caseData), [caseData]);
  const ordered = useMemo(
    () => [...rankings.cells].sort((a, b) => a.rank - b.rank),
    [rankings.cells],
  );
  const views = useMemo(
    () => rowViews(ordered, openCases, brokenDamCells(rankings.dams), copy, language),
    [ordered, openCases, rankings.dams, copy, language],
  );
  const shown = views.filter((view) => matchesFilter(filter, view.openCase !== undefined));

  function handleClick(event: MouseEvent<HTMLOListElement>) {
    const cellId = cellIdOf(event.target);
    if (cellId !== undefined) onSelect(cellId);
  }

  function handlePointer(event: SyntheticEvent<HTMLOListElement>) {
    onHighlight(cellIdOf(event.target));
  }
  const total =
    allCells.data === undefined ? null : formatNumber(allCells.data.cells.length, language);

  return (
    <>
      <div className="mv-list-head">
        <p className="mv-list-summary">
          {copy.ranked.header(rankings.week, formatNumber(ordered.length, language), total)}
        </p>
        {casework && (
          <FilterSwitch
            value={filter}
            counts={filterCounts(ordered, openCases)}
            copy={copy}
            onChange={setFilter}
          />
        )}
      </div>
      {shown.length === 0 && <p className="ops-state">{copy.ranked.empty}</p>}
      <ol
        className="mv-list"
        aria-label={copy.ranked.listLabel(rankings.week)}
        onKeyDown={moveFocus}
        onClick={handleClick}
        onMouseOver={handlePointer}
        onFocus={handlePointer}
        onMouseLeave={() => onHighlight(undefined)}
        onBlur={() => onHighlight(undefined)}
      >
        {shown.map((view) => (
          <RankedRow
            key={view.cell.cell_id}
            view={view}
            selected={rowSelection(view.cell.cell_id, selectedCellId)}
            copy={copy}
          />
        ))}
      </ol>
    </>
  );
}

type RankedAreasTabProps = {
  region: string;
  week: string | undefined;
  selectedCellId: string | undefined;
  onCellSelect: (cellId: string) => void;
  onCellHighlight: (cellId: string | undefined) => void;
};

export function RankedAreasTab({
  region,
  week,
  selectedCellId,
  onCellSelect,
  onCellHighlight,
}: RankedAreasTabProps) {
  const rankings = useQuery({
    ...rankingsQuery(region, week),
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === region ? previous : undefined,
  });
  if (isNotFoundError(rankings.error)) {
    return (
      <p className="ops-state">
        No ranked areas for {regionById(region).label}
        {week === undefined ? " yet." : ` in ${week}.`}
      </p>
    );
  }
  return (
    <div aria-busy={rankings.isPlaceholderData}>
      <QueryState
        query={rankings}
        label="ranked areas"
        emptyText="No ranked areas for this week."
        isEmpty={(data) => data.cells.length === 0}
      >
        {(data) => (
          <RankedList
            rankings={data}
            region={region}
            selectedCellId={selectedCellId}
            onSelect={onCellSelect}
            onHighlight={onCellHighlight}
          />
        )}
      </QueryState>
    </div>
  );
}
