import { useQuery } from "@tanstack/react-query";
import { brigadeInboxQuery, clockQuery } from "../../lib/api/queries";
import { QueryState } from "../ops/QueryState";
import { EscalationCard } from "./EscalationCard";

const FORBIDDEN_TEXT = "This account does not have the brigade role.";

export function BrigadeInbox() {
  const clock = useQuery(clockQuery);
  const judgeMode = clock.data?.judge_mode === true;
  const inbox = useQuery(brigadeInboxQuery(judgeMode));
  return (
    <section className="brigade-inbox">
      <div className="brigade-head">
        <h1>Brigade inbox</h1>
        {inbox.data !== undefined && (
          <span className="chip chip-plain">{inbox.data.length} open</span>
        )}
      </div>
      <QueryState
        query={inbox}
        label="the inbox"
        emptyText="No open escalations."
        forbiddenText={FORBIDDEN_TEXT}
        isEmpty={(data) => data.length === 0}
      >
        {(data) =>
          data.map((escalation) => (
            <EscalationCard key={escalation.id} escalation={escalation} example={judgeMode} />
          ))
        }
      </QueryState>
    </section>
  );
}
