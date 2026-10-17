import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { sendChat } from "../../lib/api/volunteer";
import type { VolunteerCopy } from "../../lib/copy/volunteer";
import { inboxKey } from "./inboxQuery";

type ReplyBarProps = {
  copy: VolunteerCopy;
  volunteerId: string;
  onSent: (text: string) => void;
};

export function ReplyBar({ copy, volunteerId, onSent }: ReplyBarProps) {
  const [text, setText] = useState("");
  const queryClient = useQueryClient();
  const send = useMutation({
    mutationFn: (message: string) => sendChat(volunteerId, { text: message }),
    onSuccess: (_result, message) => {
      onSent(message);
      setText((current) => (current.trim() === message ? "" : current));
      void queryClient.invalidateQueries({ queryKey: inboxKey(volunteerId) });
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = text.trim();
    if (trimmed !== "") send.mutate(trimmed);
  }

  return (
    <form className="reply-bar" onSubmit={handleSubmit}>
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
