import { useQuery } from "@tanstack/react-query";
import { publicRecordQuery } from "../../lib/api/publicQueries";
import type { RecordLine } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { PublicCopy } from "../../lib/copy/public";
import { formatMoment } from "../../lib/public/format";
import { InlineLoading } from "../LoadingPanel";

const CHIP_CLASS: Record<RecordLine["kind"], string> = {
  opened: "chip chip-open",
  task: "chip chip-assigned",
  overdue: "chip chip-overdue",
  escalated: "chip chip-escalated",
  closed: "chip chip-closed",
};

type ResponseRecordProps = {
  region: string;
  copy: PublicCopy;
  language: CopyLanguage;
  timeZone: string;
};

export function ResponseRecord({ region, copy, language, timeZone }: ResponseRecordProps) {
  const record = useQuery(publicRecordQuery(region));
  return (
    <section aria-labelledby="pub-record-title">
      <h2 id="pub-record-title" className="pub-h">
        {copy.record.title} <span className="chip chip-example">{copy.record.example}</span>
      </h2>
      {record.isPending && <InlineLoading text={copy.loading} />}
      {record.isError && (
        <p role="alert" className="ops-state">
          {copy.record.failed}{" "}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void record.refetch()}
          >
            {copy.retry}
          </button>
        </p>
      )}
      {record.data?.length === 0 && <p className="ops-state">{copy.record.empty}</p>}
      {record.data !== undefined && record.data.length > 0 && (
        <ol className="record">
          {record.data.map((line) => (
            <li key={`${line.at}-${line.cell_id}-${line.kind}`}>
              <span className={CHIP_CLASS[line.kind]}>{copy.record.kinds[line.kind]}</span>
              <p>{line.text}</p>
              <time dateTime={line.at}>{formatMoment(line.at, language, timeZone)}</time>
            </li>
          ))}
        </ol>
      )}
      <p className="pub-note">{copy.record.note}</p>
    </section>
  );
}
