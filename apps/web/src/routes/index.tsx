import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, Link, useRouter } from "@tanstack/react-router";
import { useSyncExternalStore } from "react";
import { beginTourAt } from "../lib/tour/enterStep";
import { FIRST_STEP, TOUR_STEPS } from "../lib/tour/steps";
import { getTourSnapshot, subscribeTour } from "../lib/tour/store";

const MOMENTS = [
  {
    title: "Before the dry season",
    body: "Bara ranks every area of the peatland each week by how fast it is drying, and explains each rank with the numbers behind it. Crews fix canal dams before the land burns.",
  },
  {
    title: "After a fire looks out",
    body: "When a fire goes quiet, Bara marks the burn scar and the areas that may burn again, then sends a patrol to check within 48 hours.",
  },
] as const;

const ENTRIES = [
  { to: "/public", label: "Public view", note: "No sign-in" },
  { to: "/ops", label: "Ops (judge mode)", note: "Rankings, cases, review" },
  { to: "/area/new", label: "Draw an area", note: "Rank any place" },
  { to: "/join", label: "Join as a volunteer", note: "Get tasks by message" },
] as const;

function TourButtons() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { step } = useSyncExternalStore(subscribeTour, getTourSnapshot);
  const deps = { history: router.history, queryClient };
  const resuming = step > FIRST_STEP;

  return (
    <div className="landing-actions">
      <button
        type="button"
        className="btn btn-primary btn-lg"
        onClick={() => beginTourAt(FIRST_STEP, deps)}
      >
        Start the guided tour
      </button>
      {resuming && (
        <button
          type="button"
          className="btn btn-secondary btn-lg"
          onClick={() => beginTourAt(step, deps)}
        >
          Resume at step {step + 1} of {TOUR_STEPS.length}
        </button>
      )}
      <Link to="/public" className="btn btn-secondary btn-lg">
        Explore freely
      </Link>
    </div>
  );
}

function LandingScreen() {
  return (
    <div className="landing">
      <section className="landing-hero">
        <p className="eyebrow">Peat fire prevention · tested on Riau data</p>
        <h1 className="screen-title">
          Peat fires burn for weeks. Bara tells crews where to act first.
        </h1>
        <p className="lede">The tour takes under 5 minutes and runs on the live system.</p>
        <TourButtons />
      </section>
      <section className="landing-moments" aria-label="The two moments">
        {MOMENTS.map((moment) => (
          <article key={moment.title} className="card landing-moment">
            <h2>{moment.title}</h2>
            <p>{moment.body}</p>
          </article>
        ))}
      </section>
      <nav className="landing-entries" aria-label="Open a screen">
        {ENTRIES.map((entry) => (
          <Link key={entry.to} to={entry.to} className="landing-entry">
            <strong>{entry.label}</strong>
            <span className="landing-entry-note">{entry.note}</span>
          </Link>
        ))}
      </nav>
    </div>
  );
}

export const Route = createFileRoute("/")({ component: LandingScreen });
