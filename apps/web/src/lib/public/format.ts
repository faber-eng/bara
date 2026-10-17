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

export function formatFixed(value: number, digits: number, language: CopyLanguage): string {
  return new Intl.NumberFormat(LOCALES[language], {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatPercent(rate: number, language: CopyLanguage): string {
  return `${formatNumber(rate * 100, language)}%`;
}

export function isoDay(iso: string): string {
  return iso.slice(0, 10);
}
