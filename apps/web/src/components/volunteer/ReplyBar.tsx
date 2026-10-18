import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { sendChat } from "../../lib/api/volunteer";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { inboxKey } from "./inboxQuery";

const REPLY_WAIT_MS = 30_000;

type ReplyBarProps = {
  copy: VolunteerCopy;
  volunteerId: string;
  receivedCount: number;
  onSent: (text: string, receivedCount: number) => void;
};

type Outgoing = { text: string; receivedCount: number };

export function ReplyBar({ copy, volunteerId, receivedCount, onSent }: ReplyBarProps) {
  const [text, setText] = useState("");
  const [awaitingFrom, setAwaitingFrom] = useState<number | null>(null);
  const queryClient = useQueryClient();
  const send = useMutation({
    mutationFn: (outgoing: Outgoing) => sendChat(volunteerId, { text: outgoing.text }),
    onSuccess: (_result, outgoing) => {
      onSent(outgoing.text, outgoing.receivedCount);
      setAwaitingFrom(outgoing.receivedCount);
      setText((current) => (current.trim() === outgoing.text ? "" : current));
      void queryClient.invalidateQueries({ queryKey: inboxKey(volunteerId) });
    },
  });
  const waitingForReply = awaitingFrom !== null && receivedCount <= awaitingFrom;

  useEffect(() => {
    if (!waitingForReply) return;
    const timer = setTimeout(() => setAwaitingFrom(null), REPLY_WAIT_MS);
    return () => clearTimeout(timer);
  }, [waitingForReply]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed !== "") send.mutate({ text: trimmed, receivedCount });
  }

  return (
    <form className="reply-bar" onSubmit={handleSubmit}>
      {send.isPending && (
        <p role="status" className="reply-status">
          {copy.chatSending}
        </p>
      )}
      {!send.isPending && waitingForReply && (
        <p role="status" className="reply-status">
          {copy.chatReplying}
        </p>
      )}
      <input
        className="input"
        value={text}
        placeholder={copy.chatPlaceholder}
        aria-label={copy.chatPlaceholder}
        onChange={(event) => setText(event.target.value)}
      />
      <button type="submit" className="btn btn-primary btn-sm" disabled={send.isPending}>
        {copy.chatSend}
      </button>
      {send.isError && (
        <p role="alert" className="field-error">
          {copy.chatFailed}
        </p>
      )}
    </form>
  );
}
