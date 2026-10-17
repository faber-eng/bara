import type { CopyLanguage } from "../copy/language";

const ZONE = "Asia/Jakarta";
const LOCALES: Record<CopyLanguage, string> = { id: "id-ID", en: "en-GB" };

function part(parts: Intl.DateTimeFormatPart[], type: Intl.DateTimeFormatPartTypes): string {
  return parts.find((candidate) => candidate.type === type)?.value ?? "";
}

export function formatDeadline(iso: string, language: CopyLanguage): string {
  const parts = new Intl.DateTimeFormat(LOCALES[language], {
    timeZone: ZONE,
    weekday: "long",
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const date = `${part(parts, "weekday")}, ${part(parts, "day")} ${part(parts, "month")}`;
  return `${date}, ${part(parts, "hour")}${language === "id" ? "." : ":"}${part(parts, "minute")} WIB`;
}

export function isPastDeadline(iso: string, nowMs: number): boolean {
  return Date.parse(iso) <= nowMs;
}
