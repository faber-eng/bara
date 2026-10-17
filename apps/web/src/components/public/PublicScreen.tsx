import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { ApiError } from "../../lib/api/client";
import { publicCellsQuery, publicSummaryQuery } from "../../lib/api/publicQueries";
import { useCopyLanguage } from "../../lib/copy/language";
import { type PublicCopy, publicCopy } from "../../lib/copy/public";
import { formatDay, formatMoment } from "../../lib/public/format";
import { markOnce } from "../../lib/public/perf";
import { findPublicRegion, PUBLIC_REGIONS } from "../../lib/public/regions";
import { weekChoices } from "../../lib/public/weeks";
import { LanguageToggle } from "../LanguageToggle";
import { InlineLoading } from "../LoadingPanel";
import { BulletinBlock } from "./BulletinBlock";
import { OpenDataBlock } from "./OpenDataBlock";
import { PublicMap } from "./PublicMap";
import { ResponseRecord } from "./ResponseRecord";
import { StatStrip } from "./StatStrip";

const NOT_FOUND = 404;

type PublicScreenProps = {
  regionId: string | undefined;
  week: string | undefined;
  onRegionChange: (region: string) => void;
  onWeekChange: (week: string | undefined) => void;
};

type ControlsProps = {
  copy: PublicCopy;
  regionId: string;
  week: string | undefined;
  latest: string | undefined;
  onRegionChange: (region: string) => void;
  onWeekChange: (week: string | undefined) => void;
};

function Controls({ copy, regionId, week, latest, onRegionChange, onWeekChange }: ControlsProps) {
  const lang = useCopyLanguage();
  const choices = latest === undefined ? [] : weekChoices(latest);
  return (
    <div className="pub-controls">
      <fieldset className="segmented pub-regions">
        <legend className="visually-hidden">{copy.regionLabel}</legend>
        {PUBLIC_REGIONS.map((region) => (
          <button
            key={region.id}
            type="button"
            aria-pressed={region.id === regionId}
            onClick={() => onRegionChange(region.id)}
          >
            {region.label[lang]}
          </button>
        ))}
      </fieldset>
      <label className="visually-hidden" htmlFor="pub-week">
        {copy.weekLabel}
      </label>
      <select
        id="pub-week"
        className="select pub-week"
        value={week ?? ""}
        onChange={(event) =>
          onWeekChange(event.target.value === "" ? undefined : event.target.value)
        }
      >
        <option value="">{copy.latestWeek}</option>
        {choices.map((label) => (
          <option key={label} value={label}>
            {label}
          </option>
        ))}
      </select>
      <LanguageToggle label={copy.toggleLabel} />
    </div>
  );
}

export function PublicScreen({ regionId, week, onRegionChange, onWeekChange }: PublicScreenProps) {
  const lang = useCopyLanguage();
  const copy = publicCopy(lang);
  const region = findPublicRegion(regionId);
  const query = { region: region.id, week };
  const summary = useQuery(publicSummaryQuery(query));
  const latest = useQuery({ ...publicSummaryQuery({ region: region.id, week: undefined }) });
  const cells = useQuery(publicCellsQuery(query));
  const shownWeek = summary.data?.week ?? week;

  useEffect(() => {
    if (summary.isSuccess) markOnce("public:stats");
  }, [summary.isSuccess]);

  useEffect(() => {
    if (cells.isSuccess) markOnce("public:cells");
  }, [cells.isSuccess]);

  const missing = summary.error instanceof ApiError && summary.error.status === NOT_FOUND;

  return (
    <div className="pub">
      <div className="pub-head">
        <div>
          <p className="eyebrow">
            {shownWeek === undefined ? copy.eyebrow("…") : copy.eyebrow(shownWeek)}
          </p>
          <h1 className="serif pub-title">{copy.title(region.label[lang])}</h1>
          {summary.data !== undefined && (
            <p className="freshness">
              {copy.freshness(
                formatDay(summary.data.data_as_of.s1_pass_date, lang, region.timeZone),
                formatMoment(summary.data.data_as_of.ranking_run_at, lang, region.timeZone),
              )}
            </p>
          )}
        </div>
        <Controls
          copy={copy}
          regionId={region.id}
          week={week}
          latest={latest.data?.week ?? shownWeek}
          onRegionChange={onRegionChange}
          onWeekChange={onWeekChange}
        />
      </div>
      {region.rankingOnly && <p className="banner banner-info">{copy.rankingOnly}</p>}
      {summary.isPending && <InlineLoading text={copy.loading} />}
      {missing && shownWeek !== undefined && (
        <p role="status" className="ops-state">
          {copy.noRanking(shownWeek)}
        </p>
      )}
      {summary.isError && !missing && (
        <p role="alert" className="ops-state">
          {copy.failed}{" "}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void summary.refetch()}
          >
            {copy.retry}
          </button>
        </p>
      )}
      {summary.data !== undefined && (
        <>
          <StatStrip
            summary={summary.data}
            rankingOnly={region.rankingOnly}
            copy={copy}
            language={lang}
            timeZone={region.timeZone}
          />
          <div className="pub-grid">
            {cells.data === undefined ? (
              <div className="ops-map pub-map">
                <InlineLoading text={copy.loading} />
              </div>
            ) : (
              <PublicMap
                key={region.id}
                region={region}
                query={query}
                cells={cells.data.cells}
                copy={copy}
                language={lang}
                onReady={() => markOnce("public:map")}
              />
            )}
            <BulletinBlock
              query={query}
              available={!region.rankingOnly}
              copy={copy}
              language={lang}
              timeZone={region.timeZone}
            />
          </div>
          <div className="pub-grid pub-grid-low">
            {region.rankingOnly ? (
              <div />
            ) : (
              <ResponseRecord
                region={region.id}
                copy={copy}
                language={lang}
                timeZone={region.timeZone}
              />
            )}
            <OpenDataBlock region={region.id} week={summary.data.week} copy={copy} />
          </div>
        </>
      )}
    </div>
  );
}
