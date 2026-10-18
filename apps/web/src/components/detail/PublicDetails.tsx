import type { PublicCell, PublicDam } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import { formatDay } from "../../lib/public/format";
import { DamStateChip } from "./DamDetail";
import { DetailActions, DetailLayout, DetailText, FactList } from "./DetailSheet";
import { componentFacts, type FactRow, rankChangeMeaning, scoreFact } from "./facts";

type DownloadProps = { copy: DetailCopy; onDownload: () => void };

function DownloadAction({ copy, onDownload }: DownloadProps) {
  return (
    <DetailActions label={copy.sections.next}>
      <button type="button" className="btn btn-primary" onClick={onDownload}>
        {copy.publicDetail.download}
      </button>
    </DetailActions>
  );
}

function cellRows(cell: PublicCell, copy: DetailCopy, language: CopyLanguage): FactRow[] {
  return [
    scoreFact(cell.drying_score, copy, language),
    {
      label: copy.facts.rank,
      value: String(cell.rank),
      meaning: rankChangeMeaning(cell.rank_change, copy),
    },
    ...componentFacts(cell.components, copy, language),
  ];
}

type PublicCellDetailProps = DownloadProps & {
  cell: PublicCell;
  openCase: boolean;
  language: CopyLanguage;
};

export function PublicCellDetail({
  cell,
  openCase,
  copy,
  language,
  onDownload,
}: PublicCellDetailProps) {
  return (
    <DetailLayout
      title={copy.cell.title(cell.cell_id)}
      chips={
        <span className="chip chip-plain">
          {copy.facts.rank} {cell.rank}
        </span>
      }
    >
      <DetailText label={copy.sections.what}>{copy.cell.what}</DetailText>
      <DetailText label={copy.sections.why}>{copy.cell.whyMissing}</DetailText>
      <FactList label={copy.sections.numbers} rows={cellRows(cell, copy, language)} />
      {openCase && <p className="mv-note">{copy.cell.openCaseNote}</p>}
      <DownloadAction copy={copy} onDownload={onDownload} />
    </DetailLayout>
  );
}

function damRows(
  dam: PublicDam,
  copy: DetailCopy,
  language: CopyLanguage,
  timeZone: string,
): FactRow[] {
  const checked =
    dam.last_checked_at === null
      ? copy.facts.neverChecked
      : formatDay(dam.last_checked_at, language, timeZone);
  const repair =
    dam.repair_due_at === null
      ? copy.facts.noRepairDue
      : formatDay(dam.repair_due_at, language, timeZone);
  return [
    { label: copy.facts.lastState, value: copy.damStates[dam.last_state], meaning: null },
    { label: copy.facts.lastChecked, value: checked, meaning: null },
    { label: copy.facts.repairDue, value: repair, meaning: null },
  ];
}

type PublicDamDetailProps = DownloadProps & {
  dam: PublicDam;
  language: CopyLanguage;
  timeZone: string;
};

export function PublicDamDetail({
  dam,
  copy,
  language,
  timeZone,
  onDownload,
}: PublicDamDetailProps) {
  return (
    <DetailLayout
      title={copy.dam.title(dam.id)}
      chips={<DamStateChip state={dam.last_state} copy={copy} />}
    >
      <DetailText label={copy.sections.what}>{copy.dam.what}</DetailText>
      <DetailText label={copy.sections.why}>{copy.dam.why}</DetailText>
      <FactList label={copy.sections.numbers} rows={damRows(dam, copy, language, timeZone)} />
      <DownloadAction copy={copy} onDownload={onDownload} />
    </DetailLayout>
  );
}
