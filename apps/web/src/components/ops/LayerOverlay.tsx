import { useQuery } from "@tanstack/react-query";
import { tileLayerQuery } from "../../lib/api/queries";
import type { TileLayerKind } from "../../lib/contracts";
import { definitionFor } from "../../lib/ops/mapLayers";
import { TileOverlay } from "./TileOverlay";

type LayerOverlayProps = {
  kind: TileLayerKind;
  region: string;
  week: string | undefined;
  opacity: number;
};

export function LayerOverlay({ kind, region, week, opacity }: LayerOverlayProps) {
  const tiles = useQuery({
    ...tileLayerQuery(kind, region, week),
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[2] === region ? previous : undefined,
  });
  if (tiles.data === undefined) return null;
  return (
    <TileOverlay
      label={definitionFor(kind).label}
      urlTemplate={tiles.data.url_template}
      opacity={opacity}
    />
  );
}
