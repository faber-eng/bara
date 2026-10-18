import type { LandingCopy } from "../../lib/copy/landing";
import { DamDiagram } from "./DamDiagram";

const TITLE_ID = "landing-problem-title";

export function ProblemSection({ copy }: { copy: LandingCopy["problem"] }) {
  return (
    <section className="landing-problem" aria-labelledby={TITLE_ID}>
      <div className="wrap landing-problem-grid">
        <div className="landing-problem-text">
          <h2 id={TITLE_ID} className="section-title landing-title">
            {copy.title}
          </h2>
          <ol className="landing-points">
            {copy.points.map((point) => (
              <li key={point.title}>
                <h3 className="landing-h3">{point.title}</h3>
                <p>{point.body}</p>
              </li>
            ))}
          </ol>
        </div>
        <DamDiagram copy={copy.diagram} />
      </div>
      <div className="wrap">
        <p className="landing-stakes">{copy.stakes}</p>
      </div>
    </section>
  );
}
