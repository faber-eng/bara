import type { CaseDetail, Evidence } from "../../lib/contracts";
import { type DetailCopy, detailCopy } from "../../lib/copy/detail";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import { useCaseDetail } from "../../lib/ops/useCaseDetail";
import { EvidenceCard } from "../ops/EvidenceCard";
import { QueryState } from "../ops/QueryState";
import { ReviewForm } from "../ops/ReviewForm";
import { DetailActions, DetailLayout, DetailSection, DetailText, FactList } from "./DetailSheet";
import { chanceText, type FactRow } from "./facts";
import type { OpsDetail } from "./selection";

function latestJudged(detail: CaseDetail): Evidence | undefined {
  for (let index = detail.evidence.length - 1; index >= 0; index -= 1) {
    const evidence = detail.evidence[index];
    if (evidence !== undefined && evidence.verdict !== null) return evidence;
  }
  return undefined;
}

function confidenceRows(
  evidence: Evidence | undefined,
  copy: DetailCopy,
  language: CopyLanguage,
): FactRow[] {
  const verdict = evidence?.verdict;
  if (verdict === undefined || verdict === null) return [];
  return [
    {
      label: copy.review.confidence,
      value: chanceText(verdict.confidence, language),
      meaning: verdict.needs_human ? copy.review.unsure : copy.review.sure,
    },
  ];
}

type ReviewBodyProps = {
  detail: CaseDetail;
  copy: DetailCopy;
  language: CopyLanguage;
  onOpen: (detail: OpsDetail) => void;
  onDone: () => void;
};

function ReviewBody({ detail, copy, language, onOpen, onDone }: ReviewBodyProps) {
  const evidence = latestJudged(detail);
  return (
    <>
      <DetailText label={copy.sections.what}>{copy.review.what}</DetailText>
      <FactList label={copy.sections.numbers} rows={confidenceRows(evidence, copy, language)} />
      <DetailSection label={copy.case.evidenceTitle}>
        {evidence === undefined ? (
          <p className="ops-meta">{copy.review.noVerdict}</p>
        ) : (
          <ul className="evidence-list">
            <EvidenceCard evidence={evidence} canExplain={false} onWhy={() => undefined} />
          </ul>
        )}
      </DetailSection>
      <DetailActions label={copy.sections.next}>
        <ReviewForm record={detail.case} onDone={onDone} />
        <button
          type="button"
          className="btn btn-quiet"
          onClick={() => onOpen({ kind: "case", id: detail.case.id })}
        >
          {copy.review.openCase}
        </button>
      </DetailActions>
    </>
  );
}

type ReviewDetailProps = {
  caseId: string;
  onOpen: (detail: OpsDetail) => void;
  onDone: () => void;
};

export function ReviewDetail({ caseId, onOpen, onDone }: ReviewDetailProps) {
  const language = useCopyLanguage();
  const copy = detailCopy(language);
  const detail = useCaseDetail(caseId);
  const record = detail.data?.case;
  const title =
    record === undefined ? caseId : copy.review.title(copy.caseTypes[record.type], record.cell_id);

  return (
    <DetailLayout
      title={title}
      chips={<span className="chip chip-human-review">{copy.review.chip}</span>}
    >
      <QueryState
        query={detail}
        label="the case"
        emptyText="This case has no detail."
        isEmpty={() => false}
      >
        {(data) => (
          <ReviewBody
            detail={data}
            copy={copy}
            language={language}
            onOpen={onOpen}
            onDone={onDone}
          />
        )}
      </QueryState>
    </DetailLayout>
  );
}
