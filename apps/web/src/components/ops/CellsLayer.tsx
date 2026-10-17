import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import type { CellPoint, RankedDam } from "../../lib/contracts";
import { type CellLayer, createCellLayer, createDamLayer } from "../../lib/ops/cellLayer";
import { fitToRanked, rankedBounds } from "../../lib/ops/rankedView";

export type FocusRequest = { cellId: string };

type CellsLayerProps = {
  cells: readonly CellPoint[];
  selectedCellId: string | undefined;
  focus: FocusRequest | null;
  onSelect: (cellId: string) => void;
};

export function CellsLayer({ cells, selectedCellId, focus, onSelect }: CellsLayerProps) {
  const map = useMap();
  const layerRef = useRef<CellLayer | null>(null);
  const selectedRef = useRef(selectedCellId);
  const fittedRef = useRef(false);
  const releaseFitRef = useRef<(() => void) | null>(null);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (map === null) return;
    const layer = createCellLayer(map, cells, {
      onSelect: (cellId) => onSelectRef.current(cellId),
    });
    layer.select(selectedRef.current);
    layerRef.current = layer;
    return () => {
      layerRef.current = null;
      layer.destroy();
    };
  }, [map, cells]);

  useEffect(() => {
    if (map === null || fittedRef.current) return;
    const bounds = rankedBounds(cells);
    if (bounds === undefined) return;
    fittedRef.current = true;
    releaseFitRef.current = fitToRanked(map, bounds);
  }, [map, cells]);

  useEffect(() => () => releaseFitRef.current?.(), []);

  useEffect(() => {
    selectedRef.current = selectedCellId;
    layerRef.current?.select(selectedCellId);
  }, [selectedCellId]);

  useEffect(() => {
    if (focus === null) return;
    releaseFitRef.current?.();
    layerRef.current?.focus(focus.cellId);
  }, [focus]);

  return null;
}

type DamsLayerProps = { dams: readonly RankedDam[]; onSelect: (dam: RankedDam) => void };

export function DamsLayer({ dams, onSelect }: DamsLayerProps) {
  const map = useMap();
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    if (map === null) return;
    const layer = createDamLayer(map, dams, (dam) => onSelectRef.current(dam));
    return () => layer.destroy();
  }, [map, dams]);

  return null;
}
