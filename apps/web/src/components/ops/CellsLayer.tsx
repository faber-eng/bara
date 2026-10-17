import { useMap } from "@vis.gl/react-google-maps";
import { useEffect, useRef } from "react";
import type { RankedCell, RankedDam } from "../../lib/contracts";
import { type CellLayer, createCellLayer, createDamLayer } from "../../lib/ops/cellLayer";

export type FocusRequest = { cellId: string };

type CellsLayerProps = {
  cells: readonly RankedCell[];
  selectedCellId: string | undefined;
  focus: FocusRequest | null;
  onSelect: (cellId: string) => void;
};

export function CellsLayer({ cells, selectedCellId, focus, onSelect }: CellsLayerProps) {
  const map = useMap();
  const layerRef = useRef<CellLayer | null>(null);
  const selectedRef = useRef(selectedCellId);
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
    selectedRef.current = selectedCellId;
    layerRef.current?.select(selectedCellId);
  }, [selectedCellId]);

  useEffect(() => {
    if (focus !== null) layerRef.current?.focus(focus.cellId);
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
