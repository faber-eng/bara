import { type CopyLanguage, setCopyLanguage, useCopyLanguage } from "../lib/copy/language";

const OPTIONS: readonly { value: CopyLanguage; label: string }[] = [
  { value: "id", label: "ID" },
  { value: "en", label: "EN" },
];

export function LanguageToggle({ label }: { label: string }) {
  const language = useCopyLanguage();
  return (
    <fieldset className="segmented lang-toggle">
      <legend className="visually-hidden">{label}</legend>
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={language === option.value}
          onClick={() => setCopyLanguage(option.value)}
        >
          {option.label}
        </button>
      ))}
    </fieldset>
  );
}
