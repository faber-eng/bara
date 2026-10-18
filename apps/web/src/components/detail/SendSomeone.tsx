import { useMutation, useQueryClient } from "@tanstack/react-query";
import { sendSomeone } from "../../lib/api/send";
import type { DetailCopy } from "../../lib/copy/detail";
import { type SendFailure, sendFailure } from "../../lib/ops/sendSomeone";

type SendCopy = DetailCopy["cell"]["send"];

function failureText(failure: SendFailure, copy: SendCopy): string {
  if (failure.kind === "rate_limited") return failure.detail;
  if (failure.kind === "no_flow") return copy.noFlow;
  if (failure.kind === "case_open") return copy.caseOpen;
  return copy.failed;
}

type SendSomeoneProps = { cellId: string; copy: SendCopy };

export function SendSomeone({ cellId, copy }: SendSomeoneProps) {
  const queryClient = useQueryClient();
  const send = useMutation({
    mutationFn: () => sendSomeone(cellId),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["cases"] }),
  });
  const failure = send.isError ? sendFailure(send.error) : null;

  if (send.isSuccess) {
    return (
      <p role="status" className="mv-note">
        {copy.sent}
      </p>
    );
  }
  if (failure?.kind === "case_open") {
    return (
      <p role="status" className="mv-note">
        {copy.caseOpen}
      </p>
    );
  }
  return (
    <>
      <button
        type="button"
        className="btn btn-primary"
        disabled={send.isPending}
        onClick={() => send.mutate()}
      >
        {send.isPending ? copy.sending : copy.action}
      </button>
      {failure !== null && <p role="alert">{failureText(failure, copy)}</p>}
    </>
  );
}
