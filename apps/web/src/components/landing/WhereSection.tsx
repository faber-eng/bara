import { Link } from "@tanstack/react-router";
import type { LandingCopy } from "../../lib/copy/landing";

const TITLE_ID = "landing-where-title";

type WhereCopy = LandingCopy["where"];

function Places({ copy }: { copy: WhereCopy }) {
  return (
    <div className="landing-places">
      <h2 id={TITLE_ID} className="section-title landing-title landing-title-compact">
        {copy.title}
      </h2>
      <dl className="landing-place-list">
        {copy.places.map((place) => (
          <div key={place.name}>
            <dt>{place.name}</dt>
            <dd>{place.body}</dd>
          </div>
        ))}
      </dl>
      <p className="muted landing-note">{copy.licence}</p>
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
              <Link to={entry.to} className="link landing-entry-label">
                {entry.label}
              </Link>
              <span className="muted">{entry.note}</span>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

export function WhereSection({ copy }: { copy: WhereCopy }) {
  return (
    <section className="landing-where" aria-labelledby={TITLE_ID}>
      <div className="wrap landing-where-grid">
        <Places copy={copy} />
        <Screens copy={copy} />
      </div>
    </section>
  );
}
