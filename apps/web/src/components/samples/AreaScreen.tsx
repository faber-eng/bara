import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { rankArea } from "../../lib/api/areaRank";
import { fetchSampleFile } from "../../lib/api/samples";
import { areaErrorKind } from "../../lib/area/errors";
import { areaKm2, draftState } from "../../lib/area/polygon";
import type { GeoPoint, SampleItem } from "../../lib/contracts";
import { areaCopy } from "../../lib/copy/area";
import { useCopyLanguage } from "../../lib/copy/language";
import { type AreaSummary, samplePoints, summarizeArea } from "../../lib/samples/area";
import { AreaDrawPanel } from "../area/AreaDrawPanel";
import { AreaMap } from "../area/AreaMap";
import { AreaResult } from "../area/AreaResult";
import { useElapsedSeconds } from "../area/useElapsedSeconds";
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
  const copy = areaCopy(useCopyLanguage());
  const [points, setPoints] = useState<GeoPoint[]>([]);
  const [fitToken, setFitToken] = useState(0);
  const sample = useMutation({
    mutationFn: loadArea,
    onSuccess: (loaded) => {
      setPoints(loaded.points);
      setFitToken((previous) => previous + 1);
      ranking.reset();
    },
  });
  const ranking = useMutation({ mutationFn: (corners: GeoPoint[]) => rankArea(corners) });
  const elapsed = useElapsedSeconds(ranking.isPending);
  const mapsKey = readMapsKey();
  const state = draftState(points);
  const result = ranking.data;

  function editPoints(next: GeoPoint[]) {
    setPoints(next);
    ranking.reset();
  }

  return (
    <section className="screen-center">
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
          onAddPoint={(point) => editPoints([...points, point])}
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
        onRank={() => ranking.mutate(points)}
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
      {result && <AreaResult ranking={result} copy={copy} />}
    </section>
  );
}
