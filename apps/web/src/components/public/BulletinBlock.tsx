import { useQuery } from "@tanstack/react-query";
import type { PublicQuery } from "../../lib/api/publicData";
import { publicBulletinQuery } from "../../lib/api/publicQueries";
import type { PublicBulletin } from "../../lib/contracts";
import type { CopyLanguage } from "../../lib/copy/language";
import type { PublicCopy } from "../../lib/copy/public";
import { formatMoment } from "../../lib/public/format";
import { InlineLoading } from "../LoadingPanel";

type Texts = { language: CopyLanguage; label: string; text: string };

function orderedTexts(bulletin: PublicBulletin, language: CopyLanguage, copy: PublicCopy): Texts[] {
  const texts: Texts[] = [];
  if (bulletin.text_id !== null) {
    texts.push({ language: "id", label: copy.bulletin.indonesian, text: bulletin.text_id });
  }
  if (bulletin.text_en !== null) {
    texts.push({ language: "en", label: copy.bulletin.english, text: bulletin.text_en });
  }
  return texts.sort((a, b) => Number(b.language === language) - Number(a.language === language));
}

function citedName(copy: PublicCopy, field: string): string {
  return copy.bulletin.fields[field] ?? field;
}

type HowWrittenProps = {
  bulletin: PublicBulletin;
  copy: PublicCopy;
  language: CopyLanguage;
  timeZone: string;
};

function HowWritten({ bulletin, copy, language, timeZone }: HowWrittenProps) {
  const isGemini = bulletin.source === "gemini";
  return (
    <details className="pub-how">
      <summary>{copy.bulletin.howTitle}</summary>
      <p>{isGemini ? copy.bulletin.howGemini : copy.bulletin.howTemplate}</p>
      <dl className="pub-how-facts">
        {isGemini && bulletin.model !== null && (
          <div>
            <dt>{copy.bulletin.model}</dt>
            <dd className="spec-code">{bulletin.model}</dd>
          </div>
        )}
        {bulletin.prompt_version !== null && (
          <div>
            <dt>{copy.bulletin.promptVersion}</dt>
            <dd className="spec-code">{bulletin.prompt_version}</dd>
          </div>
        )}
        <div>
          <dt>{copy.bulletin.citedFields}</dt>
          <dd>
            <ul className="pub-cited">
              {bulletin.cited.map((item) => (
                <li key={item.field}>
                  {citedName(copy, item.field)}: <span className="cite">{String(item.value)}</span>
                </li>
              ))}
            </ul>
          </dd>
        </div>
        {bulletin.created_at !== null && (
          <div>
            <dt>{copy.bulletin.writtenAt}</dt>
            <dd>{formatMoment(bulletin.created_at, language, timeZone)}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}

type BulletinBlockProps = {
  query: PublicQuery;
  available: boolean;
  copy: PublicCopy;
  language: CopyLanguage;
  timeZone: string;
};

export function BulletinBlock({ query, available, copy, language, timeZone }: BulletinBlockProps) {
  const bulletin = useQuery({ ...publicBulletinQuery(query), enabled: available });
  const data = bulletin.data;
  return (
    <section className="ai-card pub-bulletin" aria-labelledby="pub-bulletin-title">
      <div className="ai-card-head">
        <h2 id="pub-bulletin-title" className="pub-h">
          {copy.bulletin.title}
        </h2>
        {data?.source === "gemini" && (
          <span className="chip chip-gemini">{copy.bulletin.gemini}</span>
        )}
        {data?.source === "template" && (
          <span className="chip chip-plain">{copy.bulletin.template}</span>
        )}
      </div>
      {!available && <p className="ops-state">{copy.bulletin.unavailableRegion}</p>}
      {available && bulletin.isPending && <InlineLoading text={copy.loading} />}
      {bulletin.isError && (
        <p role="alert" className="ops-state">
          {copy.bulletin.failed}{" "}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => void bulletin.refetch()}
          >
            {copy.retry}
          </button>
        </p>
      )}
      {data !== undefined && data.source === null && (
        <p className="ops-state">{copy.bulletin.empty}</p>
      )}
      {data !== undefined && data.source !== null && (
        <>
          {orderedTexts(data, language, copy).map((item) => (
            <div className="brief-lang" key={item.language} lang={item.language}>
              <span>{item.label}</span>
              <p>{item.text}</p>
            </div>
          ))}
          <HowWritten bulletin={data} copy={copy} language={language} timeZone={timeZone} />
        </>
      )}
    </section>
  );
}
