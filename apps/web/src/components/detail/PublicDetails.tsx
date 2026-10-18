import type { PublicCell, PublicDam } from "../../lib/contracts";
import type { DetailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import { formatDay } from "../../lib/public/format";
import { DamStateValue } from "./DamDetail";
import {
  DetailAbout,
  DetailActions,
  DetailKeyFact,
  DetailLayout,
  DetailText,
  FactGroupsSection,
  FactSection,
} from "./DetailSheet";
import { componentGroups, type FactRow, rankChangeMeaning } from "./facts";
import { ScoreKeyFact } from "./ScoreKeyFact";

type DownloadProps = { copy: DetailCopy; onDownload: () => void };

function DownloadAction({ copy, onDownload }: DownloadProps) {
  return (
    <DetailActions>
      <button type="button" className="btn btn-primary" onClick={onDownload}>
        {copy.publicDetail.download}
      </button>
    </DetailActions>
  );
}

function cellRows(cell: PublicCell, copy: DetailCopy): FactRow[] {
  return [
    {
      label: copy.facts.rankChange,
      value: rankChangeMeaning(cell.rank_change, copy),
      meaning: null,
    },
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
  const groups = [
    { heading: copy.facts.rank, rows: cellRows(cell, copy) },
    ...componentGroups(cell.components, copy, language),
  ];
  return (
    <DetailLayout title={copy.cell.title(cell.cell_id)}>
      <ScoreKeyFact
        score={cell.drying_score}
        rank={cell.rank}
        total={null}
        copy={copy}
        language={language}
      />
      <DownloadAction copy={copy} onDownload={onDownload} />
      {openCase && <p className="mv-note">{copy.cell.openCaseNote}</p>}
      <DetailText label={copy.sections.why}>{copy.cell.whyMissing}</DetailText>
      <FactGroupsSection label={copy.sections.numbers} groups={groups} />
      <DetailAbout label={copy.sections.what}>{copy.cell.what}</DetailAbout>
    </DetailLayout>
  );
}

function damRows(dam: PublicDam, copy: DetailCopy, language: CopyLanguage, timeZone: string) {
  const repair =
    dam.repair_due_at === null
      ? copy.facts.noRepairDue
      : formatDay(dam.repair_due_at, language, timeZone);
  return [{ label: copy.facts.repairDue, value: repair, meaning: null }];
}

function checkedCaption(
  dam: PublicDam,
  copy: DetailCopy,
  language: CopyLanguage,
  timeZone: string,
) {
  if (dam.last_checked_at === null) return copy.facts.neverChecked;
  return copy.dam.checkedAt(formatDay(dam.last_checked_at, language, timeZone));
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
    <DetailLayout title={copy.dam.title(dam.id)}>
      <DetailKeyFact
        label={copy.facts.lastState}
        value={<DamStateValue state={dam.last_state} copy={copy} />}
        caption={checkedCaption(dam, copy, language, timeZone)}
      />
      <DownloadAction copy={copy} onDownload={onDownload} />
      <DetailText label={copy.sections.why}>{copy.dam.why}</DetailText>
      <FactSection label={copy.sections.numbers} rows={damRows(dam, copy, language, timeZone)} />
      <DetailAbout label={copy.sections.what}>{copy.dam.what}</DetailAbout>
    </DetailLayout>
  );
}
