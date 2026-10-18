import type { ReactNode } from "react";
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

type CardProps = { area: string; title: string; children: ReactNode };

function EvalCard({ area, title, children }: CardProps) {
  return (
    <article className={`card pub-eval-card pub-eval-${area}`}>
      <h3 className="pub-eval-h">{title}</h3>
      {children}
    </article>
  );
}

function CardHead({ copy, runAt, lede }: { copy: EvalCopy; runAt: string; lede: string }) {
  return (
    <>
      <p className="muted pub-eval-run">{copy.runOn(isoDay(runAt))}</p>
      <p className="pub-eval-lede">{lede}</p>
    </>
  );
}

function NotRun({ copy, area, title }: { copy: EvalCopy; area: string; title: string }) {
  return (
    <EvalCard area={area} title={title}>
      <p className="muted">{copy.notRun}</p>
    </EvalCard>
  );
}

function DryingPart({ drying, copy, language }: SectionProps & { drying: DryingEval | null }) {
  if (drying === null) return <NotRun copy={copy} area="drying" title={copy.drying.title} />;
  return (
    <EvalCard area="drying" title={copy.drying.title}>
      <CardHead copy={copy} runAt={drying.runAt} lede={copy.drying.lede(drying.topShare)} />
      <div className="pub-eval-scroll">
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
    </EvalCard>
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
  if (reignition === null)
    return <NotRun copy={copy} area="reignition" title={copy.reignition.title} />;
  return (
    <EvalCard area="reignition" title={copy.reignition.title}>
      <CardHead
        copy={copy}
        runAt={reignition.runAt}
        lede={copy.reignition.lede(reignition.split, reignition.events, reignition.positives)}
      />
      <div className="pub-eval-scroll">
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
    </EvalCard>
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
  if (evidence === null) return <NotRun copy={copy} area="evidence" title={copy.evidence.title} />;
  return (
    <EvalCard area="evidence" title={copy.evidence.title}>
      <CardHead copy={copy} runAt={evidence.runAt} lede={copy.evidence.lede(evidence.model)} />
      {evidence.sets.map((set) => (
        <div className="pub-eval-scroll" key={set.kind}>
          <table className="table">
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
        </div>
      ))}
    </EvalCard>
  );
}

function AgentPart({ agent, copy, language }: SectionProps & { agent: AgentEval | null }) {
  if (agent === null) return <NotRun copy={copy} area="agent" title={copy.agent.title} />;
  return (
    <EvalCard area="agent" title={copy.agent.title}>
      <CardHead copy={copy} runAt={agent.runAt} lede={copy.agent.lede(agent.model)} />
      <p className="serif num pub-eval-figure">{copy.agent.result(agent.passed, agent.cases)}</p>
      <p className="num muted">
        {copy.agent.rate} {formatPercent(agent.passRate, language)}
      </p>
    </EvalCard>
  );
}

export function EvalPanelView({ report }: { report: EvalReport }) {
  const language = useCopyLanguage();
  const copy = evalCopy(language);
  return (
    <div className="pub-eval-grid">
      <DryingPart drying={report.drying} copy={copy} language={language} />
      <ReignitionPart reignition={report.reignition} copy={copy} language={language} />
      <EvidencePart evidence={report.evidence} copy={copy} language={language} />
      <AgentPart agent={report.agent} copy={copy} language={language} />
    </div>
  );
}

const PARSED = parseEvalReport(evalJson);

export function EvalPanel() {
  const copy = evalCopy(useCopyLanguage());
  return (
    <section className="pub-eval" aria-labelledby="pub-eval-title">
      <h2 id="pub-eval-title" className="pub-h">
        {copy.title}
      </h2>
      {PARSED.ok ? <EvalPanelView report={PARSED.report} /> : <p role="alert">{copy.invalid}</p>}
      <p className="muted pub-eval-pointer">{copy.pointer}</p>
    </section>
  );
}
