import type { PublicSummary } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { PublicCopy } from "../../lib/copy/public";
import { formatDay, formatNumber } from "../../lib/public/format";
import { statReadings } from "../../lib/public/stats";

type StatStripProps = {
  summary: PublicSummary;
  rankingOnly: boolean;
  copy: PublicCopy;
  language: CopyLanguage;
  timeZone: string;
};

export function StatStrip({ summary, rankingOnly, copy, language, timeZone }: StatStripProps) {
  const asOf = formatDay(summary.data_as_of.s1_pass_date, language, timeZone);
  return (
    <dl className="stat-strip pub-stats">
      {statReadings(summary, rankingOnly).map((reading) => {
        const text = copy.stats[reading.key];
        const hint =
          reading.escalated === undefined ? text.hint : copy.escalatedHint(reading.escalated);
        return (
          <div className="stat" key={reading.key} title={copy.statSource(reading.key, asOf)}>
            <dt>{text.label}</dt>
            {reading.value === null ? (
              <dd className="stat-empty">{text.empty}</dd>
            ) : (
              <dd className="num">
                {formatNumber(reading.value, language)}
                <small>{text.unit === "%" ? "%" : ` ${text.unit}`}</small>
              </dd>
            )}
            <span>{hint}</span>
          </div>
        );
      })}
    </dl>
  );
}
