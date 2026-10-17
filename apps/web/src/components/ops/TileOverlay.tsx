import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import { LAYER_SHOWN, LAYER_START, measureSince, WEEK_START, WEEK_SWAP } from "../../lib/ops/perf";
import { tileUrl } from "../../lib/ops/tileUrl";

const TILE_SIZE = 256;

type TileOverlayProps = { label: string; urlTemplate: string; opacity: number };

function removeLayer(map: google.maps.Map, layer: google.maps.ImageMapType): void {
  const index = map.overlayMapTypes.getArray().indexOf(layer);
  if (index >= 0) map.overlayMapTypes.removeAt(index);
}

function reloadTiles(map: google.maps.Map, layer: google.maps.ImageMapType): void {
  const index = map.overlayMapTypes.getArray().indexOf(layer);
  if (index < 0) return;
  map.overlayMapTypes.removeAt(index);
  map.overlayMapTypes.insertAt(index, layer);
}

export function TileOverlay({ label, urlTemplate, opacity }: TileOverlayProps) {
  const map = useMap();
  const layerRef = useRef<google.maps.ImageMapType | null>(null);
  const opacityRef = useRef(opacity);
  const urlRef = useRef(urlTemplate);
  const appliedUrlRef = useRef(urlTemplate);

  useEffect(() => {
    opacityRef.current = opacity;
    layerRef.current?.setOpacity(opacity);
  }, [opacity]);

  useEffect(() => {
    if (map === null) return;
    appliedUrlRef.current = urlRef.current;
    const layer = new google.maps.ImageMapType({
      name: label,
      tileSize: new google.maps.Size(TILE_SIZE, TILE_SIZE),
      opacity: opacityRef.current,
      getTileUrl: (coord, zoom) => tileUrl(urlRef.current, coord.x, coord.y, zoom),
    });
    map.overlayMapTypes.push(layer);
    layerRef.current = layer;
    measureSince(LAYER_START, LAYER_SHOWN);
    return () => {
      layerRef.current = null;
      removeLayer(map, layer);
    };
  }, [map, label]);

  useEffect(() => {
    urlRef.current = urlTemplate;
    const layer = layerRef.current;
    if (map === null || layer === null || appliedUrlRef.current === urlTemplate) return;
    appliedUrlRef.current = urlTemplate;
    reloadTiles(map, layer);
    measureSince(WEEK_START, WEEK_SWAP);
  }, [map, urlTemplate]);

  return null;
}
