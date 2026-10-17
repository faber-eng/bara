import { createFileRoute } from "@tanstack/react-router";
import { PublicScreen } from "../components/public/PublicScreen";
import { findPublicRegion } from "../lib/public/regions";
import { parseWeekLabel } from "../lib/public/weeks";

type PublicSearch = { region?: string; week?: string };

function parseRegion(value: unknown): string | undefined {
  if (typeof value !== "string") return undefined;
  const region = findPublicRegion(value);
  return region.id === value ? value : undefined;
}

function PublicRoute() {
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  return (
    <PublicScreen
      regionId={search.region}
      week={search.week}
      onRegionChange={(region) => void navigate({ search: { region, week: undefined } })}
      onWeekChange={(week) => void navigate({ search: (previous) => ({ ...previous, week }) })}
    />
  );
}

export const Route = createFileRoute("/public")({
  validateSearch: (search: Record<string, unknown>): PublicSearch => ({
    region: parseRegion(search.region),
    week: parseWeekLabel(search.week),
  }),
  component: PublicRoute,
});
