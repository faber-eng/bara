import evalJson from "../../eval/eval.json";
import { type EvalCopy, evalCopy } from "../../lib/copy/eval";
import { type CopyLanguage, useCopyLanguage } from "../../lib/copy/language";
import {
  type AgentEval,
  type DryingEval,
  type EvalReport,
  type EvidenceEval,
  parseEvalReport,
  type ReignitionEval,
} from "../../lib/eval/report";
import { formatFixed, formatNumber, formatPercent, isoDay } from "../../lib/public/format";

type SectionProps = { copy: EvalCopy; language: CopyLanguage };

const NO_VALUE = "n/a";

function rateText(rate: number | null, language: CopyLanguage): string {
  if (rate === null) return NO_VALUE;
  return formatPercent(rate, language);
}

function aucText(auc: number | null, language: CopyLanguage): string {
  if (auc === null) return NO_VALUE;
  return formatFixed(auc, 3, language);
}

function liftText(lift: number | null, language: CopyLanguage): string {
  if (lift === null) return NO_VALUE;
  return `${formatNumber(lift, language)}x`;
}

function RunDate({ copy, runAt }: { copy: EvalCopy; runAt: string }) {
  return <p className="pub-license">{copy.runOn(isoDay(runAt))}</p>;
}

function NotRun({ copy, title }: { copy: EvalCopy; title: string }) {
  return (
    <div className="pub-eval-part">
      <h3 className="pub-eval-h">{title}</h3>
      <p className="stat-empty">{copy.notRun}</p>
    </div>
  );
}

function DryingPart({ drying, copy, language }: SectionProps & { drying: DryingEval | null }) {
  if (drying === null) return <NotRun copy={copy} title={copy.drying.title} />;
  return (
    <div className="pub-eval-part">
      <h3 className="pub-eval-h">{copy.drying.title}</h3>
      <RunDate copy={copy} runAt={drying.runAt} />
      <p>{copy.drying.lede(drying.topShare)}</p>
      <table className="table">
        <thead>
          <tr>
            <th>{copy.drying.year}</th>
            <th className="num">{copy.drying.weeks}</th>
            <th className="num">{copy.drying.hotspots}</th>
            <th className="num">{copy.drying.captureRate}</th>
            <th className="num">{copy.drying.lift}</th>
          </tr>
        </thead>
        <tbody>
          {drying.years.map((row) => (
            <tr key={row.year}>
              <td>{row.year}</td>
              <td className="num">{formatNumber(row.weeks, language)}</td>
              <td className="num">{formatNumber(row.hotspots, language)}</td>
              <td className="num">{rateText(row.captureRate, language)}</td>
              <td className="num">{liftText(row.lift, language)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type ScoreRow = { label: string; name: string; auc: number | null; precisionTop10: number };

function scoreRows(reignition: ReignitionEval, copy: EvalCopy): ScoreRow[] {
  const rows: ScoreRow[] = [{ label: copy.reignition.model, ...reignition.model }];
  if (reignition.served !== null) {
    rows.push({ label: copy.reignition.served, ...reignition.served });
  }
  rows.push({ label: copy.reignition.baseline, ...reignition.baseline });
  return rows;
}

function ReignitionPart({
  reignition,
  copy,
  language,
}: SectionProps & { reignition: ReignitionEval | null }) {
  if (reignition === null) return <NotRun copy={copy} title={copy.reignition.title} />;
  return (
    <div className="pub-eval-part">
      <h3 className="pub-eval-h">{copy.reignition.title}</h3>
      <RunDate copy={copy} runAt={reignition.runAt} />
      <p>{copy.reignition.lede(reignition.split, reignition.events, reignition.positives)}</p>
      <table className="table">
        <thead>
          <tr>
            <th>{copy.reignition.method}</th>
            <th className="num">{copy.reignition.auc}</th>
            <th className="num">{copy.reignition.precision}</th>
          </tr>
        </thead>
        <tbody>
          {scoreRows(reignition, copy).map((row) => (
            <tr key={row.label}>
              <td title={row.name}>{row.label}</td>
              <td className="num">{aucText(row.auc, language)}</td>
              <td className="num">{formatPercent(row.precisionTop10, language)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function labelFor(labels: Record<string, string>, key: string): string {
  return labels[key] ?? key;
}

function EvidencePart({
  evidence,
  copy,
  language,
}: SectionProps & { evidence: EvidenceEval | null }) {
  if (evidence === null) return <NotRun copy={copy} title={copy.evidence.title} />;
  return (
    <div className="pub-eval-part">
      <h3 className="pub-eval-h">{copy.evidence.title}</h3>
      <RunDate copy={copy} runAt={evidence.runAt} />
      <p>{copy.evidence.lede(evidence.model)}</p>
      {evidence.sets.map((set) => (
        <table className="table" key={set.kind}>
          <caption className="pub-eval-caption">
            {labelFor(copy.evidence.kinds, set.kind)} ({copy.evidence.setSize(set.n, set.failed)})
          </caption>
          <thead>
            <tr>
              <th>{copy.evidence.field}</th>
              <th className="num">{copy.evidence.accuracy}</th>
            </tr>
          </thead>
          <tbody>
            {set.fields.map((row) => (
              <tr key={row.field}>
                <td>{labelFor(copy.evidence.fields, row.field)}</td>
                <td className="num">
                  {rateText(row.accuracy, language)} ({row.correct}/{row.n})
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ))}
    </div>
  );
}

function AgentPart({ agent, copy, language }: SectionProps & { agent: AgentEval | null }) {
  if (agent === null) return <NotRun copy={copy} title={copy.agent.title} />;
  return (
    <div className="pub-eval-part">
      <h3 className="pub-eval-h">{copy.agent.title}</h3>
      <RunDate copy={copy} runAt={agent.runAt} />
      <p>{copy.agent.lede(agent.model)}</p>
      <p className="num">
        {copy.agent.result(agent.passed, agent.cases)} · {copy.agent.rate}{" "}
        {formatPercent(agent.passRate, language)}
      </p>
    </div>
  );
}

export function EvalPanelView({ report }: { report: EvalReport }) {
  const language = useCopyLanguage();
  const copy = evalCopy(language);
  return (
    <>
      <DryingPart drying={report.drying} copy={copy} language={language} />
      <ReignitionPart reignition={report.reignition} copy={copy} language={language} />
      <EvidencePart evidence={report.evidence} copy={copy} language={language} />
      <AgentPart agent={report.agent} copy={copy} language={language} />
    </>
  );
}

const PARSED = parseEvalReport(evalJson);

export function EvalPanel() {
  const copy = evalCopy(useCopyLanguage());
  return (
    <section className="card pub-eval" aria-labelledby="pub-eval-title">
      <h2 id="pub-eval-title" className="pub-h">
        {copy.title}
      </h2>
      {PARSED.ok ? <EvalPanelView report={PARSED.report} /> : <p role="alert">{copy.invalid}</p>}
      <p className="pub-license">{copy.pointer}</p>
    </section>
  );
}
