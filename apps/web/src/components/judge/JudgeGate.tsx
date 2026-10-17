import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { clockQuery } from "../../lib/api/queries";
import { LoadingScreen } from "../LoadingPanel";
import { JudgeBar } from "./JudgeBar";

export function JudgeGate({ children }: { children: ReactNode }) {
  const clock = useQuery(clockQuery);

  if (clock.isPending) {
    return <LoadingScreen />;
  }
  return (
    <>
      {clock.data?.judge_mode && <JudgeBar clock={clock.data} />}
      {children}
    </>
  );
}
