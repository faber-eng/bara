import type { CopyLanguage } from "./language";

export type LoadingCopy = {
  title: string;
  waking: string;
};

const ID: LoadingCopy = {
  title: "Memuat Bara…",
  waking: "Server sedang bangun. Mohon tunggu beberapa detik.",
};

const EN: LoadingCopy = {
  title: "Loading Bara…",
  waking: "The server is waking up. This can take a few seconds.",
};

export function loadingCopy(language: CopyLanguage): LoadingCopy {
  return language === "id" ? ID : EN;
}
