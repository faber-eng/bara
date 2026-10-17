import { useMap } from "@vis.gl/react-google-maps";
import { useEffect } from "react";
import type { PublicCell } from "../../lib/contracts";
import { cellRing } from "../../lib/ops/cellGrid";

const OUTLINE_STYLE = {
  clickable: false,
  fillOpacity: 0,
  strokeColor: "#212529",
  strokeWeight: 3,
  zIndex: 4,
} as const;

type OpenCaseOutlinesProps = { cells: readonly PublicCell[]; openCellIds: readonly string[] };

export function OpenCaseOutlines({ cells, openCellIds }: OpenCaseOutlinesProps) {
  const map = useMap();

  useEffect(() => {
    if (map === null) return;
    const open = new Set(openCellIds);
    const data = new google.maps.Data({ map, style: OUTLINE_STYLE });
    for (const cell of cells) {
      if (!open.has(cell.cell_id)) continue;
      const ring = cellRing(cell.centroid).map(([lon, lat]) => new google.maps.LatLng(lat, lon));
      data.add({ geometry: new google.maps.Data.Polygon([ring]) });
    }
    return () => data.setMap(null);
  }, [map, cells, openCellIds]);

  return null;
}
