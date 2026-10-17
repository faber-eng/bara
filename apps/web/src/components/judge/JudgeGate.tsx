import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { clockQuery } from "../../lib/api/queries";
import { JudgeBar } from "./JudgeBar";

export function JudgeGate({ children }: { children: ReactNode }) {
  const clock = useQuery(clockQuery);

  if (clock.isPending) {
    return (
      <p role="status" className="judge-wait">
        Starting Bara
      </p>
    );
  }
  return (
    <>
      {clock.data?.judge_mode && <JudgeBar clock={clock.data} />}
      {children}
    </>
  );
}
