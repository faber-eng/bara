import type { CopyLanguage } from "./language";

export type ScenarioCopy = {
  rankingLabel: string;
  quietLabel: string;
  started: string;
  forbidden: string;
  rateLimited: string;
  noRanking: string;
  failed: string;
};

const ID: ScenarioCopy = {
  rankingLabel: "Mulai: peringkat mingguan",
  quietLabel: "Mulai: api mereda",
  started: "Kasus sedang dibuat, sekitar 30 dtk",
  forbidden: "Peran ini tidak boleh memulai skenario.",
  rateLimited: "Terlalu banyak permintaan. Tunggu semenit lalu coba lagi.",
  noRanking: "Belum ada data peringkat. Tugas peringkat mingguan belum jalan.",
  failed: "Tidak bisa memulai skenario. Coba lagi.",
};

const EN: ScenarioCopy = {
  rankingLabel: "Start: weekly ranking",
  quietLabel: "Start: fire goes quiet",
  started: "Cases are being created, about 30 s",
  forbidden: "This role is not allowed to start the scenario.",
  rateLimited: "Too many requests. Wait a minute and try again.",
  noRanking: "No ranking data yet. The weekly ranking job has not run.",
  failed: "Could not start the scenario. Try again.",
};

export function scenarioCopy(language: CopyLanguage): ScenarioCopy {
  return language === "id" ? ID : EN;
}
