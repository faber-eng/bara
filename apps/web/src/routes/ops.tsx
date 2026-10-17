import { createFileRoute } from "@tanstack/react-router";
import { OpsMap } from "../components/ops/OpsMap";
import { OpsPanel } from "../components/ops/OpsPanel";
import { type OpsTab, parseOpsTab } from "../lib/ops/tabs";

type OpsSearch = { tab?: OpsTab; case?: string };

function parseCaseId(value: unknown): string | undefined {
  return typeof value === "string" && value !== "" ? value : undefined;
}

function OpsScreen() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();

  function handleTabChange(tab: OpsTab) {
    void navigate({ search: (previous) => ({ ...previous, tab }) });
  }

  function handleCaseSelect(caseId: string) {
    void navigate({ search: (previous) => ({ ...previous, case: caseId }) });
  }

  return (
    <>
      <h1 className="visually-hidden">Ops dashboard</h1>
      <div className="ops">
        <OpsMap />
        <OpsPanel
          tab={search.tab ?? "ranked"}
          selectedCaseId={search.case}
          onTabChange={handleTabChange}
          onCaseSelect={handleCaseSelect}
        />
      </div>
    </>
  );
}

export const Route = createFileRoute("/ops")({
  validateSearch: (search: Record<string, unknown>): OpsSearch => ({
    tab: parseOpsTab(search.tab),
    case: parseCaseId(search.case),
  }),
  component: OpsScreen,
});
