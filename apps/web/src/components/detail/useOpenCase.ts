import { useQuery } from "@tanstack/react-query";
import { casesQuery } from "../../lib/api/queries";
import type { Case } from "../../lib/contracts";
import { regionById } from "../../lib/ops/region";

export function useOpenCase(
  region: string,
  matches: (record: Case) => boolean,
): string | undefined {
  const casework = regionById(region).casework;
  const cases = useQuery({ ...casesQuery(region), enabled: casework });
  const found = cases.data?.find(
    (summary) => summary.case.status !== "closed" && matches(summary.case),
  );
  return found?.case.id;
}
