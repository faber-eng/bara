import type { CopyLanguage } from "../copy/language";

const LOCALES: Record<CopyLanguage, string> = { id: "id-ID", en: "en-GB" };

export function formatDay(iso: string, language: CopyLanguage, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALES[language], {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone,
  }).format(new Date(iso));
}

export function formatMoment(iso: string, language: CopyLanguage, timeZone: string): string {
  return new Intl.DateTimeFormat(LOCALES[language], {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone,
  }).format(new Date(iso));
}

export function formatNumber(value: number, language: CopyLanguage): string {
  return new Intl.NumberFormat(LOCALES[language], { maximumFractionDigits: 1 }).format(value);
}
