import type { TimelineEntry } from "../../lib/contracts";
import { formatSimTime } from "../../lib/simClock";

export function CaseTimeline({ entries }: { entries: TimelineEntry[] }) {
  if (entries.length === 0) return <p className="ops-meta">No events yet.</p>;
  return (
    <ol className="timeline">
      {entries.map((entry) => (
        <li key={`${entry.at}-${entry.text}`}>
          <span className="timeline-time">{formatSimTime(entry.at)}</span>
          {entry.text}
        </li>
      ))}
    </ol>
  );
}
