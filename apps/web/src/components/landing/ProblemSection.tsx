import type { LandingCopy } from "../../lib/copy/landing";
import { DamDiagram } from "./DamDiagram";
import { SectionHead } from "./SectionHead";

const TITLE_ID = "landing-problem-title";

export function ProblemSection({ copy }: { copy: LandingCopy["problem"] }) {
  return (
    <section className="landing-section landing-problem" aria-labelledby={TITLE_ID}>
      <div className="landing-wrap landing-problem-grid">
        <div className="landing-problem-text">
          <SectionHead id={TITLE_ID} eyebrow={copy.eyebrow} title={copy.title} />
          <ol className="landing-points">
            {copy.points.map((point) => (
              <li key={point.title} className="landing-point">
                <h3 className="landing-h3">{point.title}</h3>
                <p>{point.body}</p>
              </li>
            ))}
          </ol>
        </div>
        <DamDiagram copy={copy.diagram} />
        <p className="landing-stakes">{copy.stakes}</p>
      </div>
    </section>
  );
}
