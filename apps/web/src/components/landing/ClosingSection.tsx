import { Link } from "@tanstack/react-router";
import type { LandingCopy } from "../../lib/copy/landing";
import { beginTourAt } from "../../lib/tour/enterStep";
import { FIRST_STEP } from "../../lib/tour/steps";
import { useTourDeps } from "./TourButtons";

const TITLE_ID = "landing-closing-title";

export function ClosingSection({ copy }: { copy: LandingCopy["closing"] }) {
  const deps = useTourDeps();
  return (
    <section className="landing-closing" aria-labelledby={TITLE_ID}>
      <div className="wrap">
        <h2 id={TITLE_ID} className="section-title landing-title landing-title-compact">
          {copy.title}
        </h2>
        <p className="landing-prose">{copy.body}</p>
        <div className="landing-actions">
          <button
            type="button"
            className="btn btn-primary btn-lg"
            onClick={() => beginTourAt(FIRST_STEP, deps)}
          >
            {copy.tour}
          </button>
          <Link to="/public" className="link">
            {copy.publicPage}
          </Link>
        </div>
      </div>
    </section>
  );
}
