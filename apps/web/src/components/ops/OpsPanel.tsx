import { useQuery } from "@tanstack/react-query";
import { casesQuery } from "../../lib/api/queries";
import type { CaseSummary } from "../../lib/contracts";
import { regionById } from "../../lib/ops/region";
import type { OpsTab } from "../../lib/ops/tabs";
import { CasesTab } from "./CasesTab";
import { RankedAreasTab } from "./RankedAreasTab";
import { ReviewQueueTab } from "./ReviewQueueTab";

const TAB_LABELS = {
  ranked: "Ranked areas",
  cases: "Cases",
  review: "Review queue",
} as const satisfies Record<OpsTab, string>;
const TAB_ORDER: readonly OpsTab[] = ["ranked", "cases", "review"];

type TabCounts = Record<OpsTab, number | null>;

function tabCounts(cases: readonly CaseSummary[] | undefined): TabCounts {
  if (cases === undefined) return { ranked: null, cases: null, review: null };
  let review = 0;
  for (const summary of cases) {
    if (summary.case.status === "human_review") review += 1;
  }
  return { ranked: null, cases: cases.length, review };
}

type OpsPanelProps = {
  region: string;
  week: string | undefined;
  tab: OpsTab;
  selectedCaseId: string | undefined;
  selectedCellId: string | undefined;
  onCellSelect: (cellId: string) => void;
  onTabChange: (tab: OpsTab) => void;
  onCaseSelect: (caseId: string) => void;
  onReviewSelect: (caseId: string) => void;
};

type TabBodyProps = Omit<OpsPanelProps, "onTabChange"> & { onShowCases: () => void };

function TabBody({
  region,
  week,
  tab,
  selectedCaseId,
  selectedCellId,
  onCellSelect,
  onCaseSelect,
  onReviewSelect,
  onShowCases,
}: TabBodyProps) {
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
  if (tab === "review") {
    return <ReviewQueueTab region={region} onOpen={onReviewSelect} onShowCases={onShowCases} />;
  }
  return <CasesTab region={region} selectedCaseId={selectedCaseId} onSelect={onCaseSelect} />;
}

export function OpsPanel(props: OpsPanelProps) {
  const { region, tab, onTabChange } = props;
  const casework = regionById(region).casework;
  const cases = useQuery({ ...casesQuery(region), enabled: casework });
  const counts = tabCounts(casework ? cases.data : undefined);
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
            {counts[name] !== null && <span className="tab-count">{counts[name]}</span>}
          </button>
        ))}
      </div>
      <div className="ops-panel-body" role="tabpanel" aria-label={TAB_LABELS[tab]}>
        <TabBody {...props} onShowCases={() => onTabChange("cases")} />
      </div>
    </aside>
  );
}
