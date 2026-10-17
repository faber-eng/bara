import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import { tileUrl } from "../../lib/ops/tileUrl";

const TILE_SIZE = 256;

type TileOverlayProps = { label: string; urlTemplate: string; opacity: number };

function removeLayer(map: google.maps.Map, layer: google.maps.ImageMapType): void {
  const index = map.overlayMapTypes.getArray().indexOf(layer);
  if (index >= 0) map.overlayMapTypes.removeAt(index);
}

export function TileOverlay({ label, urlTemplate, opacity }: TileOverlayProps) {
  const map = useMap();
  const layerRef = useRef<google.maps.ImageMapType | null>(null);
  const opacityRef = useRef(opacity);

  useEffect(() => {
    opacityRef.current = opacity;
    layerRef.current?.setOpacity(opacity);
  }, [opacity]);

  useEffect(() => {
    if (map === null) return;
    const layer = new google.maps.ImageMapType({
      name: label,
      tileSize: new google.maps.Size(TILE_SIZE, TILE_SIZE),
      opacity: opacityRef.current,
      getTileUrl: (coord, zoom) => tileUrl(urlTemplate, coord.x, coord.y, zoom),
    });
    map.overlayMapTypes.push(layer);
    layerRef.current = layer;
    return () => {
      layerRef.current = null;
      removeLayer(map, layer);
    };
  }, [map, label, urlTemplate]);

  return null;
}
