import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ApiError } from "../../lib/api/client";
import { clockQuery } from "../../lib/api/queries";
import type { Inbox } from "../../lib/contracts";
import { useCopyLanguage } from "../../lib/copy/language";
import { type VolunteerCopy, volunteerCopy } from "../../lib/copy/volunteer";
import { LanguageToggle } from "../LanguageToggle";
import { InlineLoading } from "../LoadingPanel";
import { ChatThread, type SentEntry, threadEntries } from "./ChatThread";
import { HomeLocation } from "./HomeLocation";
import { inboxQuery } from "./inboxQuery";
import { OutboxStatus } from "./OutboxStatus";
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
  const [sent, setSent] = useState<SentEntry[]>([]);
  const openTasks = inbox.tasks.filter(isShown);
  const entries = threadEntries(inbox.messages, sent, language);

  function handleSent(text: string, receivedCount: number) {
    const entry: SentEntry = {
      id: `sent-${sent.length}`,
      mine: true,
      text,
      at: new Date().toISOString(),
      after: receivedCount,
    };
    setSent((previous) => [...previous, entry]);
  }

  return (
    <>
      <ChatThread copy={copy} language={language} entries={entries} />
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
          isArea={inbox.area_case_ids.includes(task.case_id)}
          nowMs={nowMs}
        />
      ))}
      <ReplyBar
        copy={copy}
        volunteerId={volunteerId}
        receivedCount={inbox.messages.length}
        onSent={handleSent}
      />
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
      {inbox.data && (
        <HomeLocation
          copy={copy}
          home={inbox.data.home}
          name={inbox.data.name}
          volunteerRole={inbox.data.role}
        />
      )}
      {inbox.isPending && <InlineLoading text={copy.loading} />}
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
      <OutboxStatus copy={copy} volunteerId={volunteerId} />
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
