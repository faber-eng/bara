import type { LandingCopy, LandingStep } from "../../lib/copy/landing";

const TITLE_ID = "landing-loop-title";

type StepRowProps = { step: LandingStep; number: number; copy: LandingCopy["loop"] };

function StepRow({ step, number, copy }: StepRowProps) {
  return (
    <li className="landing-step">
      <div className="landing-step-head">
        <span className="num landing-step-number" aria-hidden="true">
          {number}
        </span>
        <h3 className="landing-h3">{step.title}</h3>
      </div>
      <dl className="landing-step-lanes">
        <div className="landing-lane landing-lane-ai">
          <dt className="landing-lane-label">{copy.aiDoes}</dt>
          <dd>{step.ai}</dd>
        </div>
        <div className="landing-lane landing-lane-people">
          <dt className="landing-lane-label">{copy.peopleDo}</dt>
          <dd>{step.people}</dd>
        </div>
      </dl>
    </li>
  );
}

export function LoopSection({ copy }: { copy: LandingCopy["loop"] }) {
  return (
    <section className="band on-dark landing-loop" aria-labelledby={TITLE_ID}>
      <div className="wrap">
        <h2 id={TITLE_ID} className="section-title landing-title">
          {copy.title}
        </h2>
        <div className="landing-lane-heads" aria-hidden="true">
          <div>
            <span>{copy.aiDoes}</span>
            <span>{copy.peopleDo}</span>
          </div>
        </div>
        <ol className="landing-steps" aria-label={copy.listLabel}>
          {copy.steps.map((step, index) => (
            <StepRow key={step.title} step={step} number={index + 1} copy={copy} />
          ))}
        </ol>
        <p className="serif landing-closing">{copy.closing}</p>
      </div>
    </section>
  );
}
