import type { ReactNode } from "react";
import type { DetailCopy } from "../../lib/copy/detail";
import type { CopyLanguage } from "../../lib/copy/language";
import { DetailKeyFact } from "./DetailSheet";
import { rankLine, scoreFact } from "./facts";

type ScoreKeyFactProps = {
  score: number;
  rank: number;
  total: number | null;
  copy: DetailCopy;
  language: CopyLanguage;
  aside?: ReactNode;
};

export function ScoreKeyFact({ score, rank, total, copy, language, aside }: ScoreKeyFactProps) {
  const fact = scoreFact(score, copy, language);
  const caption = `${fact.meaning} · ${rankLine(rank, total, copy, language)}`;
  return (
    <DetailKeyFact label={copy.facts.score} value={fact.value} caption={caption} aside={aside} />
  );
}
