import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "../../lib/api/client";
import { clockQuery } from "../../lib/api/queries";
import type { Inbox } from "../../lib/api/volunteerTypes";
import { useCopyLanguage } from "../../lib/copy/language";
import { type VolunteerCopy, volunteerCopy } from "../../lib/copy/volunteer";
import { LanguageToggle } from "../LanguageToggle";
import { ChatThread, type ThreadEntry, threadEntries } from "./ChatThread";
import { inboxQuery } from "./inboxQuery";
import { ReplyBar } from "./ReplyBar";
import { TaskCard } from "./TaskCard";

const HIDDEN_STATUSES = ["reassigned", "cancelled"];

function isShown(task: Inbox["tasks"][number]): boolean {
  return !HIDDEN_STATUSES.includes(task.status);
}

function failureText(error: Error, copy: VolunteerCopy): string {
  const forbidden = error instanceof ApiError && error.status === 403;
  return forbidden ? copy.notYours : copy.loadFailed;
}

type InboxViewProps = {
  copy: VolunteerCopy;
  volunteerId: string;
  inbox: Inbox;
  nowMs: number;
};

function InboxView({ copy, volunteerId, inbox, nowMs }: InboxViewProps) {
  const language = useCopyLanguage();
  const [sent, setSent] = useState<ThreadEntry[]>([]);
  const openTasks = inbox.tasks.filter(isShown);
  const entries = threadEntries(inbox.messages, sent, language);

  function handleSent(text: string) {
    setSent((previous) => [...previous, { id: `sent-${previous.length}`, mine: true, text }]);
  }

  return (
    <>
      <ChatThread copy={copy} entries={entries} />
      {openTasks.length === 0 && (
        <div className="empty-box">
          <h2>{copy.emptyTitle}</h2>
          <p>{copy.emptyBody}</p>
        </div>
      )}
      {openTasks.map((task) => (
        <TaskCard
          key={task.id}
          copy={copy}
          language={language}
          volunteerId={volunteerId}
          task={task}
          nowMs={nowMs}
        />
      ))}
      <ReplyBar copy={copy} volunteerId={volunteerId} onSent={handleSent} />
    </>
  );
}

export function VolunteerScreen({ volunteerId }: { volunteerId: string }) {
  const language = useCopyLanguage();
  const copy = volunteerCopy(language);
  const inbox = useQuery(inboxQuery(volunteerId));
  const clock = useQuery(clockQuery);
  const nowMs = clock.data ? Date.parse(clock.data.now) : Date.now();

  return (
    <section className="volunteer" aria-label={copy.tasksLabel}>
      <h1 className="visually-hidden">{copy.tasksLabel}</h1>
      <LanguageToggle label={copy.toggleLabel} />
      {inbox.isPending && <p role="status">{copy.loading}</p>}
      {inbox.isError && inbox.data === undefined && (
        <div role="alert" className="banner banner-danger">
          <p>{failureText(inbox.error, copy)}</p>
          <button
            type="button"
            className="btn btn-white btn-sm"
            onClick={() => void inbox.refetch()}
          >
            {copy.retry}
          </button>
        </div>
      )}
      {inbox.data && (
        <InboxView
          key={volunteerId}
          copy={copy}
          volunteerId={volunteerId}
          inbox={inbox.data}
          nowMs={nowMs}
        />
      )}
    </section>
  );
}
