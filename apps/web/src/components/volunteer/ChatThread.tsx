import { useEffect, useRef, useState } from "react";
import type { Message } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { formatClock } from "../../lib/volunteer/deadline";
import { isNearBottom, scrollDecision } from "../../lib/volunteer/scroll";

export type ThreadEntry = { id: string; mine: boolean; text: string; at: string };
export type SentEntry = ThreadEntry & { after: number };

function toReceivedEntry(message: Message, language: CopyLanguage): ThreadEntry {
  return {
    id: message.id,
    mine: false,
    text: language === "en" ? message.text_en : message.text,
    at: message.created_at,
  };
}

export function threadEntries(
  messages: Message[],
  sent: SentEntry[],
  language: CopyLanguage,
): ThreadEntry[] {
  const received = [...messages].sort(
    (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at),
  );
  const entries: ThreadEntry[] = [];
  received.forEach((message, index) => {
    for (const mine of sent) {
      if (mine.after === index) entries.push(mine);
    }
    entries.push(toReceivedEntry(message, language));
  });
  for (const mine of sent) {
    if (mine.after >= received.length) entries.push(mine);
  }
  return entries;
}

type ChatThreadProps = {
  copy: VolunteerCopy;
  language: CopyLanguage;
  entries: ThreadEntry[];
};

function ThreadView({ copy, language, entries }: ChatThreadProps) {
  const box = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [hasNew, setHasNew] = useState(false);
  const newest = entries[entries.length - 1];
  const newestId = newest?.id;
  const newestIsMine = newest?.mine === true;

  function jumpToBottom() {
    const element = box.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
    pinned.current = true;
    setHasNew(false);
  }

  function handleScroll() {
    const element = box.current;
    if (!element) return;
    pinned.current = isNearBottom(element);
    if (pinned.current) setHasNew(false);
  }

  // biome-ignore lint/correctness/useExhaustiveDependencies: runs only when the newest message changes
  useEffect(() => {
    if (scrollDecision({ pinned: pinned.current, newestIsMine }) === "follow") jumpToBottom();
    else setHasNew(true);
  }, [newestId, newestIsMine]);

  return (
    <div className="chat">
      <div
        ref={box}
        className="chat-scroll"
        role="log"
        aria-label={copy.threadLabel}
        onScroll={handleScroll}
      >
        <ul className="chat-thread">
          {entries.map((entry) => (
            <li key={entry.id} className={entry.mine ? "msg msg-me" : "msg"}>
              <span className="msg-from">{entry.mine ? copy.chatYou : copy.chatFrom}</span>
              <p className="msg-text">{entry.text}</p>
              <time className="msg-time" dateTime={entry.at}>
                {formatClock(entry.at, language)}
              </time>
            </li>
          ))}
        </ul>
      </div>
      {hasNew && (
        <button type="button" className="chat-jump btn btn-primary btn-sm" onClick={jumpToBottom}>
          {copy.newMessage}
        </button>
      )}
    </div>
  );
}

export function ChatThread(props: ChatThreadProps) {
  if (props.entries.length === 0) return null;
  return <ThreadView {...props} />;
}
