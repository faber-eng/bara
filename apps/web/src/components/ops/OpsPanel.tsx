import { regionById } from "../../lib/ops/region";
import type { OpsTab } from "../../lib/ops/tabs";
import { CaseDrawer } from "./CaseDrawer";
import { CasesTab } from "./CasesTab";
import { RankedAreasTab } from "./RankedAreasTab";
import { ReviewQueueTab } from "./ReviewQueueTab";

const TAB_LABELS = {
  ranked: "Ranked areas",
  cases: "Cases",
  review: "Review queue",
} as const satisfies Record<OpsTab, string>;
const TAB_ORDER: readonly OpsTab[] = ["ranked", "cases", "review"];

type OpsPanelProps = {
  region: string;
  week: string | undefined;
  tab: OpsTab;
  selectedCaseId: string | undefined;
  selectedCellId: string | undefined;
  onCellSelect: (cellId: string) => void;
  onTabChange: (tab: OpsTab) => void;
  onCaseSelect: (caseId: string) => void;
  onCaseClear: () => void;
};

type TabBodyProps = Pick<
  OpsPanelProps,
  | "region"
  | "week"
  | "tab"
  | "selectedCaseId"
  | "selectedCellId"
  | "onCellSelect"
  | "onCaseSelect"
  | "onCaseClear"
>;

function TabBody({
  region,
  week,
  tab,
  selectedCaseId,
  selectedCellId,
  onCellSelect,
  onCaseSelect,
  onCaseClear,
}: TabBodyProps) {
  if (selectedCaseId !== undefined && regionById(region).casework)
    return <CaseDrawer caseId={selectedCaseId} onBack={onCaseClear} />;
  if (tab === "ranked") {
    return (
      <RankedAreasTab
        region={region}
        week={week}
        selectedCellId={selectedCellId}
        onCellSelect={onCellSelect}
      />
    );
  }
  if (tab === "review") return <ReviewQueueTab region={region} onCaseSelect={onCaseSelect} />;
  return <CasesTab region={region} selectedCaseId={selectedCaseId} onSelect={onCaseSelect} />;
}

export function OpsPanel({
  region,
  week,
  tab,
  selectedCaseId,
  selectedCellId,
  onCellSelect,
  onTabChange,
  onCaseSelect,
  onCaseClear,
}: OpsPanelProps) {
  return (
    <aside className="ops-panel">
      <div className="tabs" role="tablist" aria-label="Ops lists">
        {TAB_ORDER.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={name === tab}
            onClick={() => onTabChange(name)}
          >
            {TAB_LABELS[name]}
          </button>
        ))}
      </div>
      <div className="ops-panel-body" role="tabpanel" aria-label={TAB_LABELS[tab]}>
        <TabBody
          region={region}
          week={week}
          tab={tab}
          selectedCaseId={selectedCaseId}
          selectedCellId={selectedCellId}
          onCellSelect={onCellSelect}
          onCaseSelect={onCaseSelect}
          onCaseClear={onCaseClear}
        />
      </div>
    </aside>
  );
}
