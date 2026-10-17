import { useMap } from "@vis.gl/react-google-maps";
import { useEffect } from "react";
import { tileUrl } from "../../lib/ops/tileUrl";

const TILE_SIZE = 256;
const OVERLAY_OPACITY = 0.7;

function removeLayer(map: google.maps.Map, layer: google.maps.ImageMapType): void {
  const index = map.overlayMapTypes.getArray().indexOf(layer);
  if (index >= 0) map.overlayMapTypes.removeAt(index);
}

export function DryingOverlay({ urlTemplate }: { urlTemplate: string }) {
  const map = useMap();

  useEffect(() => {
    if (map === null) return;
    const layer = new google.maps.ImageMapType({
      name: "Drying score",
      tileSize: new google.maps.Size(TILE_SIZE, TILE_SIZE),
      opacity: OVERLAY_OPACITY,
      getTileUrl: (coord, zoom) => tileUrl(urlTemplate, coord.x, coord.y, zoom),
    });
    map.overlayMapTypes.push(layer);
    return () => removeLayer(map, layer);
  }, [map, urlTemplate]);

  return null;
}
