import { useQuery } from "@tanstack/react-query";
import { brigadeContactQuery, brigadeInboxQuery, clockQuery } from "../../lib/api/queries";
import { isExampleContact } from "../../lib/brigade/contact";
import { QueryState } from "../ops/QueryState";
import { EscalationCard } from "./EscalationCard";

const FORBIDDEN_TEXT = "This account does not have the brigade role.";

function ContactError({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="ops-state">
      <p>Could not load the inbox.</p>
      <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function BrigadeInbox() {
  const clock = useQuery(clockQuery);
  const contact = useQuery(brigadeContactQuery(clock.data?.judge_mode === true));
  const inbox = useQuery(brigadeInboxQuery(contact.data));
  const example = isExampleContact(contact.data);
  return (
    <section className="brigade-inbox">
      <div className="brigade-head">
        <h1>Brigade inbox</h1>
        {inbox.data !== undefined && (
          <span className="chip chip-plain">{inbox.data.length} open</span>
        )}
      </div>
      {contact.isError && <ContactError onRetry={() => void contact.refetch()} />}
      {!contact.isError && (
        <QueryState
          query={inbox}
          label="the inbox"
          emptyText="No open escalations."
          forbiddenText={FORBIDDEN_TEXT}
          isEmpty={(data) => data.length === 0}
        >
          {(data) =>
            data.map((escalation) => (
              <EscalationCard key={escalation.id} escalation={escalation} example={example} />
            ))
          }
        </QueryState>
      )}
    </section>
  );
}
