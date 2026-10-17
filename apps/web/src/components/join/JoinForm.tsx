import { useMutation } from "@tanstack/react-query";
import { type ChangeEvent, type FormEvent, useState } from "react";
import type { Language } from "../../lib/contracts";
import type { JoinCopy } from "../../lib/copy/join";
import { setCopyLanguage } from "../../lib/copy/language";
import { classifyJoinError } from "../../lib/join/errors";
import {
  EMPTY_JOIN_FORM,
  type JoinField,
  type JoinFormValues,
  LANGUAGES,
  validateJoinForm,
} from "../../lib/join/form";
import { submitJoin } from "../../lib/join/submit";
import { HomePicker } from "./HomePicker";

type JoinFormProps = { copy: JoinCopy; onJoined: (volunteerId: string) => void };

function FieldError({
  field,
  errors,
  copy,
}: {
  field: JoinField;
  errors: JoinField[];
  copy: JoinCopy;
}) {
  if (!errors.includes(field)) return null;
  return (
    <p id={`join-${field}-error`} className="field-error" role="alert">
      {copy.fieldErrors[field]}
    </p>
  );
}

function isLanguage(value: string): value is Language {
  return LANGUAGES.some((language) => language === value);
}

function mirrorCopyLanguage(language: Language): void {
  if (language === "id" || language === "en") setCopyLanguage(language);
}

export function JoinForm({ copy, onJoined }: JoinFormProps) {
  const [values, setValues] = useState<JoinFormValues>(EMPTY_JOIN_FORM);
  const [errors, setErrors] = useState<JoinField[]>([]);
  const join = useMutation({
    mutationFn: submitJoin,
    onSuccess: (response) => onJoined(response.volunteer_id),
  });

  function update(patch: Partial<JoinFormValues>) {
    setValues((previous) => ({ ...previous, ...patch }));
  }

  function handleLanguage(event: ChangeEvent<HTMLSelectElement>) {
    const language = event.target.value;
    if (!isLanguage(language)) return;
    update({ language });
    mirrorCopyLanguage(language);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const result = validateJoinForm(values);
    if ("errors" in result) {
      setErrors(result.errors);
      return;
    }
    setErrors([]);
    join.mutate(result.request);
  }

  return (
    <form className="card join-card" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label className="field-label" htmlFor="join-code">
          {copy.fields.inviteCode.label}
        </label>
        <input
          id="join-code"
          className="input"
          autoComplete="off"
          value={values.inviteCode}
          aria-invalid={errors.includes("inviteCode")}
          aria-describedby="join-code-hint"
          onChange={(event) => update({ inviteCode: event.target.value })}
        />
        <p id="join-code-hint" className="field-hint">
          {copy.fields.inviteCode.hint}
        </p>
        <FieldError field="inviteCode" errors={errors} copy={copy} />
      </div>
      <div className="field">
        <label className="field-label" htmlFor="join-name">
          {copy.fields.name.label}
        </label>
        <input
          id="join-name"
          className="input"
          autoComplete="name"
          value={values.name}
          aria-invalid={errors.includes("name")}
          onChange={(event) => update({ name: event.target.value })}
        />
        <FieldError field="name" errors={errors} copy={copy} />
      </div>
      <fieldset className="field join-fieldset">
        <legend className="field-label">{copy.fields.home.label}</legend>
        <p className="field-hint">{copy.fields.home.hint}</p>
        <HomePicker
          copy={copy}
          value={values.home}
          invalid={errors.includes("home")}
          onChange={(home) => update({ home })}
        />
        <FieldError field="home" errors={errors} copy={copy} />
      </fieldset>
      <div className="field">
        <label className="field-label" htmlFor="join-language">
          {copy.fields.language.label}
        </label>
        <select
          id="join-language"
          className="select"
          value={values.language}
          onChange={handleLanguage}
        >
          {LANGUAGES.map((language) => (
            <option key={language} value={language}>
              {copy.languages[language]}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label className="field-label" htmlFor="join-whatsapp">
          {copy.fields.whatsapp.label}
        </label>
        <input
          id="join-whatsapp"
          className="input"
          type="tel"
          autoComplete="tel"
          value={values.whatsapp}
          aria-invalid={errors.includes("whatsapp")}
          aria-describedby="join-whatsapp-hint"
          onChange={(event) => update({ whatsapp: event.target.value })}
        />
        <p id="join-whatsapp-hint" className="field-hint">
          {copy.fields.whatsapp.hint}
        </p>
        <FieldError field="whatsapp" errors={errors} copy={copy} />
      </div>
      {join.isError && (
        <p role="alert" className="field-error">
          {copy.failures[classifyJoinError(join.error)]}
        </p>
      )}
      <button type="submit" className="btn btn-primary btn-lg btn-block" disabled={join.isPending}>
        {join.isPending ? copy.submitting : copy.submit}
      </button>
    </form>
  );
}
