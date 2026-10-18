import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { rankArea } from "../../lib/api/areaRank";
import { fetchSampleFile } from "../../lib/api/samples";
import { areaErrorKind } from "../../lib/area/errors";
import { areaKm2, draftState } from "../../lib/area/polygon";
import type { GeoPoint, SampleItem } from "../../lib/contracts";
import { areaCopy } from "../../lib/copy/area";
import { detailCopy } from "../../lib/copy/detail";
import { useCopyLanguage } from "../../lib/copy/language";
import { type AreaSummary, samplePoints, summarizeArea } from "../../lib/samples/area";
import { AreaDrawPanel } from "../area/AreaDrawPanel";
import { AreaMap } from "../area/AreaMap";
import { AreaResult } from "../area/AreaResult";
import { useElapsedSeconds } from "../area/useElapsedSeconds";
import { AreaCellDetail } from "../detail/AreaCellDetail";
import { DetailSheet } from "../detail/DetailSheet";
import { LanguageToggle } from "../LanguageToggle";
import { SamplePicker } from "./SamplePicker";

type LoadedArea = { item: SampleItem; summary: AreaSummary; points: GeoPoint[] };

async function loadArea(item: SampleItem): Promise<LoadedArea> {
  const geojson: unknown = JSON.parse(await (await fetchSampleFile(item)).text());
  return { item, summary: summarizeArea(geojson), points: samplePoints(geojson) };
}

function readMapsKey(): string {
  const key: unknown = import.meta.env.VITE_MAPS_KEY;
  return typeof key === "string" ? key : "";
}

export function AreaScreen() {
  const language = useCopyLanguage();
  const copy = areaCopy(language);
  const detail = detailCopy(language);
  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [selectedCellId, setSelectedCellId] = useState<string | undefined>(undefined);
  const [fitToken, setFitToken] = useState(0);
  const sample = useMutation({
    mutationFn: loadArea,
    onSuccess: (loaded) => {
      setPoints(loaded.points);
      setFitToken((previous) => previous + 1);
      setSelectedCellId(undefined);
      ranking.reset();
    },
  });
  const ranking = useMutation({ mutationFn: (corners: GeoPoint[]) => rankArea(corners) });
  const elapsed = useElapsedSeconds(ranking.isPending);
  const mapsKey = readMapsKey();
  const state = draftState(points);
  const result = ranking.data;
  const selectedCell = result?.cells.find((cell) => cell.cell_id === selectedCellId);

  function editPoints(next: GeoPoint[]) {
    setPoints(next);
    setSelectedCellId(undefined);
    ranking.reset();
  }

  function handleRank() {
    setSelectedCellId(undefined);
    ranking.mutate(points);
  }

  return (
    <section className="screen-center mv-area">
      <LanguageToggle label={copy.toggleLabel} />
      <h1 className="screen-title">{copy.title}</h1>
      <p className="lede">{copy.lede}</p>
      {mapsKey === "" ? (
        <p role="status" className="map-note">
          {copy.mapKeyMissing}
        </p>
      ) : (
        <AreaMap
          mapsKey={mapsKey}
          points={points}
          fitToken={fitToken}
          cells={result?.cells ?? []}
          tileUrlTemplate={result?.tile_url_template ?? null}
          tileLabel={copy.title}
          disabled={ranking.isPending}
          keyCopy={detail}
          onAddPoint={(point) => editPoints([...points, point])}
          onCellSelect={setSelectedCellId}
        />
      )}
      <AreaDrawPanel
        copy={copy}
        corners={points.length}
        km2={areaKm2(points)}
        state={state}
        pending={ranking.isPending}
        onUndo={() => editPoints(points.slice(0, -1))}
        onClear={() => editPoints([])}
        onRank={handleRank}
      />
      <SamplePicker
        kind="area"
        copy={copy}
        disabled={sample.isPending || ranking.isPending}
        onPick={(item) => sample.mutate(item)}
      />
      {sample.isPending && <p role="status">{copy.sampleLoading}</p>}
      {sample.isError && <p role="alert">{copy.loadFailed}</p>}
      {sample.data && (
        <section className="card join-card" aria-label={copy.loadedTitle}>
          <span className="chip chip-example">{copy.sampleChip}</span>
          <h2 className="join-heading">{sample.data.summary.name}</h2>
          <p>{copy.vertices(sample.data.summary.vertices)}</p>
          <p className="field-hint">{copy.credit(sample.data.item.credit)}</p>
        </section>
      )}
      {ranking.isPending && <p role="status">{copy.ranking(elapsed)}</p>}
      {ranking.isError && (
        <p role="alert" data-testid="area-error">
          {copy.errors[areaErrorKind(ranking.error)]}
        </p>
      )}
      {result && (
        <AreaResult
          ranking={result}
          copy={copy}
          detail={detail}
          selectedCellId={selectedCellId}
          onSelect={setSelectedCellId}
        />
      )}
      {result && selectedCell !== undefined && (
        <DetailSheet closeLabel={detail.close} onClose={() => setSelectedCellId(undefined)}>
          <AreaCellDetail cell={selectedCell} ranking={result} copy={detail} language={language} />
        </DetailSheet>
      )}
    </section>
  );
}
