import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import type { FocusRequest } from "../components/ops/CellsLayer";
import { OpsMap } from "../components/ops/OpsMap";
import { OpsPanel } from "../components/ops/OpsPanel";
import { parseCellId } from "../lib/ops/cellSelection";
import { type OpsTab, parseOpsTab } from "../lib/ops/tabs";

type OpsSearch = { tab?: OpsTab; case?: string; cell?: string };

function parseCaseId(value: unknown): string | undefined {
  return parseCellId(value);
}

function OpsScreen() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
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
          selectedCellId={search.cell}
          focus={focus}
          onCellSelect={handleMapCellSelect}
          onCellClear={handleCellClear}
        />
        <OpsPanel
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
  }),
  component: OpsScreen,
});
