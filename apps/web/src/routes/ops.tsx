import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { OpsDetailSheet } from "../components/detail/OpsDetailSheet";
import { detailFromSearch, type OpsDetail, searchForDetail } from "../components/detail/selection";
import type { FocusRequest } from "../components/ops/CellsLayer";
import { OpsMap } from "../components/ops/OpsMap";
import { OpsPanel } from "../components/ops/OpsPanel";
import { rankingsQuery } from "../lib/api/queries";
import { parseCellId } from "../lib/ops/cellSelection";
import { DEFAULT_REGION_ID, parseRegionId } from "../lib/ops/region";
import { type OpsTab, parseOpsTab } from "../lib/ops/tabs";
import { effectiveWeek, parseWeek } from "../lib/ops/weeks";

type OpsSearch = {
  tab?: OpsTab;
  case?: string;
  cell?: string;
  dam?: string;
  review?: string;
  region?: string;
  week?: string;
};

function parseId(value: unknown): string | undefined {
  return parseCellId(value);
}

function OpsScreen() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const region = search.region ?? DEFAULT_REGION_ID;
  const latest = useQuery(rankingsQuery(region)).data?.week;
  const week = effectiveWeek(search.week, latest);
  const [focus, setFocus] = useState<FocusRequest | null>(null);

  const detail = detailFromSearch(search);

  function openDetail(next: OpsDetail | null) {
    void navigate({ search: (previous) => ({ ...previous, ...searchForDetail(next) }) });
  }

  function handleTabChange(tab: OpsTab) {
    void navigate({ search: (previous) => ({ ...previous, tab }) });
  }

  function handleListCellSelect(cellId: string) {
    setFocus({ cellId });
    openDetail({ kind: "cell", id: cellId });
  }

  function handleZoom(cellId: string) {
    setFocus({ cellId });
    openDetail(null);
  }

  function handleRegionChange(regionId: string) {
    setFocus(null);
    void navigate({
      search: (previous) => ({
        ...previous,
        ...searchForDetail(null),
        region: regionId === DEFAULT_REGION_ID ? undefined : regionId,
        week: undefined,
      }),
    });
  }

  function handleWeekChange(week: string | undefined) {
    void navigate({ search: (previous) => ({ ...previous, week }) });
  }

  return (
    <>
      <h1 className="visually-hidden">Ops dashboard</h1>
      <div className="ops">
        <OpsMap
          region={region}
          week={week}
          onRegionChange={handleRegionChange}
          onWeekChange={handleWeekChange}
          selectedCellId={search.cell}
          focus={focus}
          onCellSelect={(cellId) => openDetail({ kind: "cell", id: cellId })}
          onDamSelect={(damId) => openDetail({ kind: "dam", id: damId })}
          onCaseSelect={(caseId) => openDetail({ kind: "case", id: caseId })}
        />
        <OpsPanel
          region={region}
          week={week}
          tab={search.tab ?? "ranked"}
          selectedCaseId={search.case}
          selectedCellId={search.cell}
          onCellSelect={handleListCellSelect}
          onTabChange={handleTabChange}
          onCaseSelect={(caseId) => openDetail({ kind: "case", id: caseId })}
          onReviewSelect={(caseId) => openDetail({ kind: "review", id: caseId })}
        />
      </div>
      {detail !== null && (
        <OpsDetailSheet
          region={region}
          detail={detail}
          onOpen={openDetail}
          onZoom={handleZoom}
          onClose={() => openDetail(null)}
        />
      )}
    </>
  );
}

export const Route = createFileRoute("/ops")({
  validateSearch: (search: Record<string, unknown>): OpsSearch => ({
    tab: parseOpsTab(search.tab),
    case: parseId(search.case),
    cell: parseId(search.cell),
    dam: parseId(search.dam),
    review: parseId(search.review),
    region: parseRegionId(search.region),
    week: parseWeek(search.week),
  }),
  component: OpsScreen,
});
