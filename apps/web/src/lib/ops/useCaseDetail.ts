import { useQuery } from "@tanstack/react-query";
import { caseDetailQuery, OPS_REFRESH_MS } from "../api/queries";
import { useCaseFollow } from "./useCaseFollow";

export function useCaseDetail(caseId: string) {
  const streaming = useCaseFollow(caseId);
  return useQuery({
    ...caseDetailQuery(caseId),
    refetchInterval: streaming ? false : OPS_REFRESH_MS,
    refetchIntervalInBackground: false,
  });
}
