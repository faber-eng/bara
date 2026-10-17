import { useMutation } from "@tanstack/react-query";
import { fetchSampleFile } from "../../lib/api/samples";
import type { SampleItem } from "../../lib/contracts";
import { areaCopy } from "../../lib/copy/area";
import { useCopyLanguage } from "../../lib/copy/language";
import { type AreaSummary, summarizeArea } from "../../lib/samples/area";
import { LanguageToggle } from "../LanguageToggle";
import { SamplePicker } from "./SamplePicker";

type LoadedArea = { item: SampleItem; summary: AreaSummary };

async function loadArea(item: SampleItem): Promise<LoadedArea> {
  const text = await (await fetchSampleFile(item)).text();
  return { item, summary: summarizeArea(JSON.parse(text)) };
}

export function AreaScreen() {
  const copy = areaCopy(useCopyLanguage());
  const area = useMutation({ mutationFn: loadArea });

  return (
    <section className="screen-center">
      <LanguageToggle label={copy.toggleLabel} />
      <h1 className="screen-title">{copy.title}</h1>
      <p className="lede">{copy.lede}</p>
      <SamplePicker
        kind="area"
        copy={copy}
        disabled={area.isPending}
        onPick={(item) => area.mutate(item)}
      />
      {area.isPending && <p role="status">{copy.sampleLoading}</p>}
      {area.isError && <p role="alert">{copy.loadFailed}</p>}
      {area.data && (
        <section className="card join-card" aria-label={copy.loadedTitle}>
          <span className="chip chip-example">{copy.sampleChip}</span>
          <h2 className="join-heading">{area.data.summary.name}</h2>
          <p>{copy.vertices(area.data.summary.vertices)}</p>
          <p className="field-hint">{copy.credit(area.data.item.credit)}</p>
          <p>{copy.rankingSoon}</p>
        </section>
      )}
    </section>
  );
}
