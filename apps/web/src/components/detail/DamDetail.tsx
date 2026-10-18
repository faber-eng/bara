import { useQuery } from "@tanstack/react-query";
import { rankingsQuery } from "../../lib/api/queries";
import type { RankedDam } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import { damColor } from "../../lib/ops/cellLayer";
import { formatSimTime } from "../../lib/simClock";
import { InlineLoading } from "../LoadingPanel";
import {
  DetailAbout,
  DetailActions,
  DetailKeyFact,
  DetailLayout,
  DetailText,
  FactSection,
} from "./DetailSheet";
import { type FactRow, scoreFact } from "./facts";
import type { OpsDetail } from "./selection";
import { useOpenCase } from "./useOpenCase";

export function DamStateValue({
  state,
  copy,
}: {
  state: RankedDam["last_state"];
  copy: DetailCopy;
}) {
  return (
    <span className="mv-dam-chip">
      <span className="mv-swatch-dot" style={{ background: damColor(state) }} aria-hidden="true" />
      {copy.damStates[state]}
    </span>
  );
}

function lastCheckedCaption(dam: RankedDam, copy: DetailCopy): string {
  if (dam.last_checked_at === null) return copy.facts.neverChecked;
  return copy.dam.checkedAt(formatSimTime(dam.last_checked_at));
}

function damRows(dam: RankedDam, copy: DetailCopy, language: CopyLanguage): FactRow[] {
  return [
    scoreFact(dam.drying_score, copy, language),
    { label: copy.facts.rank, value: String(dam.rank), meaning: dam.cell_id },
  ];
}

function DamKeyFact({ dam, copy }: { dam: RankedDam; copy: DetailCopy }) {
  return (
    <DetailKeyFact
      label={copy.facts.lastState}
      value={<DamStateValue state={dam.last_state} copy={copy} />}
      caption={lastCheckedCaption(dam, copy)}
    />
  );
}

type DamBodyProps = {
  dam: RankedDam;
  region: string;
  copy: DetailCopy;
  language: CopyLanguage;
  onOpen: (detail: OpsDetail) => void;
};

function DamBody({ dam, region, copy, language, onOpen }: DamBodyProps) {
  const caseId = useOpenCase(region, (record) => record.dam_id === dam.dam_id);
  return (
    <>
      <DamKeyFact dam={dam} copy={copy} />
      <DetailActions>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => onOpen({ kind: "cell", id: dam.cell_id })}
        >
          {copy.dam.showArea}
        </button>
        {caseId !== undefined && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => onOpen({ kind: "case", id: caseId })}
          >
            {copy.dam.openCase}
          </button>
        )}
      </DetailActions>
      <DetailText label={copy.sections.why}>{copy.dam.why}</DetailText>
      <FactSection label={copy.sections.numbers} rows={damRows(dam, copy, language)} />
    </>
  );
}

type DamDetailProps = { damId: string; region: string; onOpen: (detail: OpsDetail) => void };

export function DamDetail({ damId, region, onOpen }: DamDetailProps) {
  const language = useCopyLanguage();
  const copy = detailCopy(language);
  const rankings = useQuery(rankingsQuery(region));
  const dam = rankings.data?.dams.find((item) => item.dam_id === damId);

  return (
    <DetailLayout title={copy.dam.title(damId)}>
      {rankings.isPending && <InlineLoading text="Loading the dam" />}
      {!rankings.isPending && dam === undefined && <p className="mv-note">{copy.dam.missing}</p>}
      {dam !== undefined && (
        <DamBody dam={dam} region={region} copy={copy} language={language} onOpen={onOpen} />
      )}
      <DetailAbout label={copy.sections.what}>{copy.dam.what}</DetailAbout>
    </DetailLayout>
  );
}
