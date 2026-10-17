import type { OpsTab } from "../../lib/ops/tabs";
import { CasesTab } from "./CasesTab";
import { RankedAreasTab } from "./RankedAreasTab";

const TAB_LABELS = { ranked: "Ranked areas", cases: "Cases" } as const satisfies Record<
  OpsTab,
  string
>;
const TAB_ORDER: readonly OpsTab[] = ["ranked", "cases"];

type OpsPanelProps = {
  tab: OpsTab;
  selectedCaseId: string | undefined;
  onTabChange: (tab: OpsTab) => void;
  onCaseSelect: (caseId: string) => void;
};

export function OpsPanel({ tab, selectedCaseId, onTabChange, onCaseSelect }: OpsPanelProps) {
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
        {tab === "ranked" ? (
          <RankedAreasTab />
        ) : (
          <CasesTab selectedCaseId={selectedCaseId} onSelect={onCaseSelect} />
        )}
      </div>
    </aside>
  );
}
