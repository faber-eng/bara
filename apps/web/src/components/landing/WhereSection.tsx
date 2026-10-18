import { Link } from "@tanstack/react-router";
import type { LandingCopy } from "../../lib/copy/landing";
import { SectionHead } from "./SectionHead";

const TITLE_ID = "landing-where-title";

type WhereCopy = LandingCopy["where"];

function Places({ copy }: { copy: WhereCopy }) {
  return (
    <div className="landing-places">
      <SectionHead id={TITLE_ID} eyebrow={copy.eyebrow} title={copy.title} />
      <dl className="landing-place-list">
        {copy.places.map((place) => (
          <div key={place.name} className="landing-place">
            <dt>{place.name}</dt>
            <dd>{place.body}</dd>
          </div>
        ))}
      </dl>
      <p className="landing-small">{copy.licence}</p>
    </div>
  );
}

function Screens({ copy }: { copy: WhereCopy }) {
  return (
    <div className="landing-screens">
      <h3 className="landing-h3">{copy.screensTitle}</h3>
      <nav aria-label={copy.screensTitle}>
        <ul className="landing-entries">
          {copy.entries.map((entry) => (
            <li key={entry.to}>
              <Link to={entry.to} className="landing-entry">
                <span className="landing-entry-label">{entry.label}</span>
                <span className="landing-entry-note">{entry.note}</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

export function WhereSection({ copy }: { copy: WhereCopy }) {
  return (
    <section className="landing-section landing-where" aria-labelledby={TITLE_ID}>
      <div className="landing-wrap landing-where-grid">
        <Places copy={copy} />
        <Screens copy={copy} />
      </div>
    </section>
  );
}
