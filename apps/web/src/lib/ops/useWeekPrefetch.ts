import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { rankingsQuery, tileLayerQuery } from "../api/queries";
import { definitionFor, type EnabledLayers, enabledKinds } from "./mapLayers";
import { neighbourWeeks, requestWeek, weekRange } from "./weeks";

type PrefetchInput = {
  region: string;
  week: string | undefined;
  latest: string | undefined;
  enabled: EnabledLayers;
};

export function useWeekPrefetch({ region, week, latest, enabled }: PrefetchInput): void {
  const queryClient = useQueryClient();

  useEffect(() => {
    const current = week ?? latest;
    if (current === undefined) return;
    const weekly = enabledKinds(enabled).filter((kind) => definitionFor(kind).weekly);
    for (const neighbour of neighbourWeeks(weekRange(latest), current)) {
      const asked = requestWeek(neighbour, latest);
      void queryClient.prefetchQuery(rankingsQuery(region, asked));
      for (const kind of weekly) {
        void queryClient.prefetchQuery(tileLayerQuery(kind, region, asked));
      }
    }
  }, [queryClient, region, week, latest, enabled]);
}
