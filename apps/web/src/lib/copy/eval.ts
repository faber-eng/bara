import type { CopyLanguage } from "./language";

export type EvalCopy = {
  title: string;
  notRun: string;
  invalid: string;
  runOn: (day: string) => string;
  pointer: string;
  drying: {
    title: string;
    lede: (share: number) => string;
    year: string;
    weeks: string;
    hotspots: string;
    captureRate: string;
    lift: string;
  };
  reignition: {
    title: string;
    lede: (split: string, events: number, positives: number) => string;
    model: string;
    method: string;
    auc: string;
    precision: string;
    baseline: string;
    served: string;
  };
  evidence: {
    title: string;
    lede: (model: string) => string;
    field: string;
    accuracy: string;
    setSize: (n: number, failed: number) => string;
    kinds: Record<string, string>;
    fields: Record<string, string>;
  };
  agent: {
    title: string;
    lede: (model: string) => string;
    result: (passed: number, cases: number) => string;
    rate: string;
  };
};

const EN: EvalCopy = {
  title: "How well it works",
  notRun: "Not run yet",
  invalid: "The evaluation file could not be read.",
  runOn: (day) => `Run on ${day}`,
  pointer: "Method and re-run commands: docs/EVAL.md",
  drying: {
    title: "Drying ranking",
    lede: (share) => `Share of later hotspots inside the top ${Math.round(share * 100)}% of cells.`,
    year: "Year",
    weeks: "Weeks (n)",
    hotspots: "Detection-weeks (n)",
    captureRate: "Captured",
    lift: "Lift",
  },
  reignition: {
    title: "Re-ignition risk",
    lede: (split, events, positives) =>
      `${split} split: ${events} events, ${positives} re-ignited. Compared with a plain count of detection days.`,
    model: "Re-ignition model",
    method: "Method",
    auc: "AUC",
    precision: "Precision at 10%",
    baseline: "Detection-days baseline",
    served: "Model in service",
  },
  evidence: {
    title: "Gemini verdict accuracy",
    lede: (model) => `${model} against labelled evidence.`,
    field: "Field",
    accuracy: "Accuracy",
    setSize: (n, failed) => `n = ${n}, ${failed} failed`,
    kinds: { photo: "Photos", audio: "Voice notes" },
    fields: {
      subject: "Subject",
      dam_state: "Dam state",
      smoke: "Smoke",
      hot_ground_signs: "Hot ground",
      open_flame: "Open flame",
    },
  },
  agent: {
    title: "Agent checks",
    lede: (model) => `Scripted cases run on ${model}.`,
    result: (passed, cases) => `${passed} of ${cases} cases passed`,
    rate: "Pass rate",
  },
};

const ID: EvalCopy = {
  title: "Seberapa baik hasilnya",
  notRun: "Belum dijalankan",
  invalid: "Berkas evaluasi tidak bisa dibaca.",
  runOn: (day) => `Dijalankan ${day}`,
  pointer: "Metode dan perintah ulang: docs/EVAL.md",
  drying: {
    title: "Peringkat pengeringan",
    lede: (share) =>
      `Bagian titik panas berikutnya yang jatuh di ${Math.round(share * 100)}% petak teratas.`,
    year: "Tahun",
    weeks: "Minggu (n)",
    hotspots: "Deteksi-minggu (n)",
    captureRate: "Tertangkap",
    lift: "Lift",
  },
  reignition: {
    title: "Risiko api menyala lagi",
    lede: (split, events, positives) =>
      `Data ${split}: ${events} kejadian, ${positives} menyala lagi. Dibandingkan dengan hitungan hari deteksi biasa.`,
    model: "Re-ignition model",
    method: "Method",
    auc: "AUC",
    precision: "Presisi di 10%",
    baseline: "Pembanding hari deteksi",
    served: "Model yang dipakai",
  },
  evidence: {
    title: "Akurasi vonis Gemini",
    lede: (model) => `${model} diuji pada bukti yang sudah diberi label.`,
    field: "Isian",
    accuracy: "Akurasi",
    setSize: (n, failed) => `n = ${n}, ${failed} gagal`,
    kinds: { photo: "Foto", audio: "Catatan suara" },
    fields: {
      subject: "Objek",
      dam_state: "Kondisi sekat",
      smoke: "Asap",
      hot_ground_signs: "Tanah panas",
      open_flame: "Api terbuka",
    },
  },
  agent: {
    title: "Uji agen",
    lede: (model) => `Kasus uji berskrip dijalankan di ${model}.`,
    result: (passed, cases) => `${passed} dari ${cases} kasus lulus`,
    rate: "Tingkat lulus",
  },
};

export function evalCopy(language: CopyLanguage): EvalCopy {
  return language === "id" ? ID : EN;
}
