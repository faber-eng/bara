import type { PublicCopy } from "../../lib/copy/public";
import { apiRootPath, CREDITS, exportPath, LICENSE } from "../../lib/public/links";

type OpenDataBlockProps = { region: string; week: string; copy: PublicCopy };

export function OpenDataBlock({ region, week, copy }: OpenDataBlockProps) {
  return (
    <section className="card pub-data" aria-labelledby="pub-data-title">
      <h2 id="pub-data-title" className="pub-h">
        {copy.data.title}
      </h2>
      <p>{copy.data.lede(week)}</p>
      <div className="pub-actions">
        <a className="btn btn-primary btn-sm" href={exportPath(region, week, "csv")} download>
          {copy.data.csv}
        </a>
        <a className="btn btn-secondary btn-sm" href={exportPath(region, week, "geojson")} download>
          {copy.data.geojson}
        </a>
      </div>
      <a className="link" href={apiRootPath(region)}>
        {copy.data.api(apiRootPath(region))}
      </a>
      <p className="pub-license">
        <a href={LICENSE.url} target="_blank" rel="noreferrer">
          {LICENSE.name}
        </a>
        . {copy.data.license}
      </p>
      <p className="pub-license">{copy.data.credits}</p>
      <ul className="pub-credits">
        {CREDITS.map((credit) => (
          <li key={credit}>{credit}</li>
        ))}
      </ul>
    </section>
  );
}
