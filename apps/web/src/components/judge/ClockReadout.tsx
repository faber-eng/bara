import { formatSimTime } from "../../lib/simClock";

function ClockIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M10 5.5V10l3 2"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function ClockReadout({ now }: { now: string }) {
  return (
    <span className="judge-clock">
      <ClockIcon />
      Sim · {formatSimTime(now)}
    </span>
  );
}
