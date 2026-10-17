import { useQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import type { FocusRequest } from "../components/ops/CellsLayer";
import { OpsMap } from "../components/ops/OpsMap";
import { OpsPanel } from "../components/ops/OpsPanel";
import { rankingsQuery } from "../lib/api/queries";
import { parseCellId } from "../lib/ops/cellSelection";
import { DEFAULT_REGION_ID, parseRegionId } from "../lib/ops/region";
import { type OpsTab, parseOpsTab } from "../lib/ops/tabs";
import { effectiveWeek, parseWeek } from "../lib/ops/weeks";

type OpsSearch = { tab?: OpsTab; case?: string; cell?: string; region?: string; week?: string };

function parseCaseId(value: unknown): string | undefined {
  return parseCellId(value);
}

function OpsScreen() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const region = search.region ?? DEFAULT_REGION_ID;
  const latest = useQuery(rankingsQuery(region)).data?.week;
  const week = effectiveWeek(search.week, latest);
  const [focus, setFocus] = useState<FocusRequest | null>(null);

  function handleTabChange(tab: OpsTab) {
    void navigate({ search: (previous) => ({ ...previous, tab, case: undefined }) });
  }

  function handleCaseSelect(caseId: string) {
    void navigate({ search: (previous) => ({ ...previous, case: caseId }) });
  }

  function handleMapCellSelect(cellId: string) {
    void navigate({ search: (previous) => ({ ...previous, cell: cellId }) });
  }

  function handleListCellSelect(cellId: string) {
    setFocus({ cellId });
    handleMapCellSelect(cellId);
  }

  function handleRegionChange(regionId: string) {
    setFocus(null);
    void navigate({
      search: (previous) => ({
        ...previous,
        region: regionId === DEFAULT_REGION_ID ? undefined : regionId,
        week: undefined,
        cell: undefined,
        case: undefined,
      }),
    });
  }

  function handleWeekChange(week: string | undefined) {
    void navigate({ search: (previous) => ({ ...previous, week }) });
  }

  function handleCellClear() {
    void navigate({ search: (previous) => ({ ...previous, cell: undefined }) });
  }

  function handleCaseClear() {
    void navigate({ search: (previous) => ({ ...previous, case: undefined }) });
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
          onCellSelect={handleMapCellSelect}
          onCellClear={handleCellClear}
        />
        <OpsPanel
          region={region}
          week={week}
          tab={search.tab ?? "ranked"}
          selectedCaseId={search.case}
          selectedCellId={search.cell}
          onCellSelect={handleListCellSelect}
          onTabChange={handleTabChange}
          onCaseSelect={handleCaseSelect}
          onCaseClear={handleCaseClear}
        />
      </div>
    </>
  );
}

export const Route = createFileRoute("/ops")({
  validateSearch: (search: Record<string, unknown>): OpsSearch => ({
    tab: parseOpsTab(search.tab),
    case: parseCaseId(search.case),
    cell: parseCellId(search.cell),
    region: parseRegionId(search.region),
    week: parseWeek(search.week),
  }),
  component: OpsScreen,
});
