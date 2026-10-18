import { detailCopy } from "../../lib/copy/detail";
import { useCopyLanguage } from "../../lib/copy/language";
import { CaseItemDetail } from "./CaseItemDetail";
import { CellDetail } from "./CellDetail";
import { DamDetail } from "./DamDetail";
import { DetailSheet } from "./DetailSheet";
import { ReviewDetail } from "./ReviewDetail";
import type { OpsDetail } from "./selection";

type OpsDetailSheetProps = {
  region: string;
  week: string | undefined;
  detail: OpsDetail;
  onOpen: (detail: OpsDetail) => void;
  onZoom: (cellId: string) => void;
  onClose: () => void;
};

function OpsDetailBody({ region, week, detail, onOpen, onZoom, onClose }: OpsDetailSheetProps) {
  const key = `${detail.kind}-${detail.id}`;
  switch (detail.kind) {
    case "cell":
      return (
        <CellDetail
          key={key}
          cellId={detail.id}
          region={region}
          week={week}
          onOpen={onOpen}
          onZoom={onZoom}
        />
      );
    case "dam":
      return <DamDetail key={key} damId={detail.id} region={region} onOpen={onOpen} />;
    case "case":
      return <CaseItemDetail key={key} caseId={detail.id} onOpen={onOpen} />;
    case "review":
      return <ReviewDetail key={key} caseId={detail.id} onOpen={onOpen} onDone={onClose} />;
    default:
      return unhandledDetail(detail.kind);
  }
}

function unhandledDetail(kind: never): never {
  throw new Error(`unhandled ops detail: ${String(kind)}`);
}

export function OpsDetailSheet(props: OpsDetailSheetProps) {
  const copy = detailCopy(useCopyLanguage());
  return (
    <DetailSheet closeLabel={copy.close} onClose={props.onClose}>
      <OpsDetailBody {...props} />
    </DetailSheet>
  );
}
