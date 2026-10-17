import type { Message } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { VolunteerCopy } from "../../lib/copy/volunteer";

export type ThreadEntry = { id: string; mine: boolean; text: string };

export function threadEntries(
  messages: Message[],
  sent: ThreadEntry[],
  language: CopyLanguage,
): ThreadEntry[] {
  const received = [...messages]
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
    .map((message) => ({
      id: message.id,
      mine: false,
      text: language === "en" ? message.text_en : message.text,
    }));
  return [...received, ...sent];
}

type ChatThreadProps = { copy: VolunteerCopy; entries: ThreadEntry[] };

export function ChatThread({ copy, entries }: ChatThreadProps) {
  if (entries.length === 0) return null;
  return (
    <ul className="chat-thread" aria-label={copy.threadLabel}>
      {entries.map((entry) => (
        <li key={entry.id} className={entry.mine ? "msg msg-me" : "msg"}>
          <span className="msg-from">{entry.mine ? copy.chatYou : copy.chatFrom}</span>
          {entry.text}
        </li>
      ))}
    </ul>
  );
}
