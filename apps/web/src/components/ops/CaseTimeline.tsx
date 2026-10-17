import type { TimelineEntry } from "../../lib/contracts";
import { RULE_ESCALATION_LABEL } from "../../lib/ops/timelineOrigin";
import { formatSimTime } from "../../lib/simClock";

type CaseTimelineProps = { entries: TimelineEntry[]; ruleMade?: ReadonlySet<TimelineEntry> };

export function CaseTimeline({ entries, ruleMade }: CaseTimelineProps) {
  if (entries.length === 0) return <p className="ops-meta">No events yet.</p>;
  return (
    <ol className="timeline">
      {entries.map((entry) => (
        <li key={`${entry.at}-${entry.text}`}>
          <span className="timeline-time">{formatSimTime(entry.at)}</span>
          {entry.text}
          {ruleMade?.has(entry) === true && (
            <span className="chip chip-escalated timeline-origin">{RULE_ESCALATION_LABEL}</span>
          )}
        </li>
      ))}
    </ol>
  );
}
