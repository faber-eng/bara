import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ackEscalation } from "../../lib/api/escalations";
import type { Escalation } from "../../lib/contracts";
import { evidenceImageUrl } from "../../lib/ops/caseDrawer";
import { CaseTimeline } from "../ops/CaseTimeline";
import { MiniMap } from "./MiniMap";

function Photo({ uri }: { uri: string }) {
  const url = evidenceImageUrl(uri);
  if (url === null) return <span className="thumb thumb-empty">photo</span>;
  return <img className="brigade-photo" src={url} alt="Patrol evidence" loading="lazy" />;
}

function Photos({ photos }: { photos: string[] }) {
  if (photos.length === 0) {
    return <p className="brigade-nophoto">No photo. Nobody sent evidence for this case.</p>;
  }
  return (
    <div className="brigade-photos">
      {photos.map((uri) => (
        <Photo key={uri} uri={uri} />
      ))}
    </div>
  );
}

function AckButton({ escalationId, caseId }: { escalationId: string; caseId: string }) {
  const queryClient = useQueryClient();
  const ack = useMutation({
    mutationFn: () => ackEscalation(escalationId),
    onSettled: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["brigade"] }),
        queryClient.invalidateQueries({ queryKey: ["cases"] }),
      ]),
  });
  return (
    <div className="drawer-close">
      <button
        type="button"
        className="btn btn-primary"
        aria-label={`Acknowledge escalation for ${caseId}`}
        disabled={ack.isPending}
        onClick={() => ack.mutate()}
      >
        {ack.isPending ? "Acknowledging" : "Acknowledge"}
      </button>
      {ack.isError && <p role="alert">Could not acknowledge. Try again.</p>}
    </div>
  );
}

type EscalationCardProps = { escalation: Escalation; example: boolean };

export function EscalationCard({ escalation, example }: EscalationCardProps) {
  return (
    <article className="brigade-card" aria-label={`Escalation for ${escalation.case_id}`}>
      <div className="brigade-main">
        <p className="brigade-chips">
          <span className="chip chip-escalated">Escalated</span>
          {example && <span className="chip chip-example">Example data</span>}
        </p>
        <h2 className="brigade-title">{escalation.case_id}</h2>
        <Photos photos={escalation.pack.photos} />
        <div className="brief-lang">
          <span className="brief-label">Bahasa Indonesia · written by Gemini</span>
          <p lang="id">{escalation.brief_id}</p>
        </div>
        <div className="brief-lang">
          <span className="brief-label">English · written by Gemini</span>
          <p lang="en">{escalation.brief_en}</p>
        </div>
        <AckButton escalationId={escalation.id} caseId={escalation.case_id} />
      </div>
      <div className="brigade-side">
        <MiniMap mapUrl={escalation.pack.map_url} />
        <CaseTimeline entries={escalation.pack.timeline} />
      </div>
    </article>
  );
}
