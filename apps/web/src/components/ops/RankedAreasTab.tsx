import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { isNotFoundError } from "../../lib/api/client";
import { rankingsQuery } from "../../lib/api/queries";
import type { RankedCell } from "../../lib/contracts";
import { detailCopy } from "../../lib/copy/detail";
import { useCopyLanguage } from "../../lib/copy/language";
import { rowSelection } from "../../lib/ops/cellSelection";
import { regionById } from "../../lib/ops/region";
import { ScoreBadge } from "../detail/badges";
import { rankChangeShort } from "../detail/facts";
import { QueryState } from "./QueryState";

type RowProps = { cell: RankedCell; selected: boolean; onSelect: (cellId: string) => void };

function RankedRow({ cell, selected, onSelect }: RowProps) {
  const copy = detailCopy(useCopyLanguage());
  const rowRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (selected) rowRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [selected]);

  return (
    <li ref={rowRef}>
      <button
        type="button"
        className="ops-cell-button mv-row"
        aria-pressed={selected}
        onClick={() => onSelect(cell.cell_id)}
      >
        <span className="mv-row-rank num" aria-hidden="true">
          {cell.rank}
        </span>
        <span className="mv-row-main">
          <strong className="mv-row-title">{cell.cell_id}</strong>
          <span className="mv-row-meta">{rankChangeShort(cell.rank_change, copy)}</span>
        </span>
        <ScoreBadge score={cell.drying_score} />
      </button>
    </li>
  );
}

type ListProps = {
  cells: RankedCell[];
  week: string;
  selectedCellId: string | undefined;
  onSelect: (cellId: string) => void;
};

function RankedList({ cells, week, selectedCellId, onSelect }: ListProps) {
  const ordered = [...cells].sort((a, b) => a.rank - b.rank);
  return (
    <>
      <ol className="mv-list" aria-label={`Ranked areas, ${week}`}>
        {ordered.map((cell) => (
          <RankedRow
            key={cell.cell_id}
            cell={cell}
            selected={rowSelection(cell.cell_id, selectedCellId)}
            onSelect={onSelect}
          />
        ))}
      </ol>
      <p className="ops-foot">
        {ordered.length} areas for {week}, fastest drying first. Score 0 to 100.
      </p>
    </>
  );
}

type RankedAreasTabProps = {
  region: string;
  week: string | undefined;
  selectedCellId: string | undefined;
  onCellSelect: (cellId: string) => void;
};

export function RankedAreasTab({
  region,
  week,
  selectedCellId,
  onCellSelect,
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
            cells={data.cells}
            week={data.week}
            selectedCellId={selectedCellId}
            onSelect={onCellSelect}
          />
        )}
      </QueryState>
    </div>
  );
}
