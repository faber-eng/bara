import type { GeoPoint, JoinRequest, Language } from "../contracts";

export const LANGUAGES: readonly Language[] = ["id", "en", "ms", "fr"];
export const DEFAULT_LANGUAGE: Language = "en";

const WHATSAPP_PATTERN = /^\+[1-9]\d{7,14}$/;
const NAME_MAX = 80;
const CODE_MAX = 128;

export type JoinFormValues = {
  inviteCode: string;
  name: string;
  home: GeoPoint | null;
  language: Language;
  whatsapp: string;
};

export type JoinField = "inviteCode" | "name" | "home" | "whatsapp";

export type JoinValidation = { request: JoinRequest } | { errors: JoinField[] };

export const EMPTY_JOIN_FORM: JoinFormValues = {
  inviteCode: "",
  name: "",
  home: null,
  language: DEFAULT_LANGUAGE,
  whatsapp: "",
};

export function normalizeWhatsapp(raw: string): string {
  return raw.replace(/[\s-]/g, "");
}

function isCodeValid(code: string): boolean {
  return code.trim().length > 0 && code.length <= CODE_MAX;
}

function isNameValid(name: string): boolean {
  const trimmed = name.trim();
  return trimmed.length > 0 && trimmed.length <= NAME_MAX;
}

function isWhatsappValid(raw: string): boolean {
  const number = normalizeWhatsapp(raw);
  return number === "" || WHATSAPP_PATTERN.test(number);
}

function failedFields(values: JoinFormValues): JoinField[] {
  const failed: JoinField[] = [];
  if (!isCodeValid(values.inviteCode)) failed.push("inviteCode");
  if (!isNameValid(values.name)) failed.push("name");
  if (values.home === null) failed.push("home");
  if (!isWhatsappValid(values.whatsapp)) failed.push("whatsapp");
  return failed;
}

function whatsappOrNull(raw: string): string | null {
  const number = normalizeWhatsapp(raw);
  return number === "" ? null : number;
}

export function validateJoinForm(values: JoinFormValues): JoinValidation {
  const errors = failedFields(values);
  if (errors.length > 0 || values.home === null) return { errors };
  return {
    request: {
      invite_code: values.inviteCode.trim(),
      name: values.name.trim(),
      home: values.home,
      language: values.language,
      whatsapp: whatsappOrNull(values.whatsapp),
    },
  };
}
