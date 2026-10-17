import type { CopyLanguage } from "./language";

export type StatKey =
  | "high_risk_cells"
  | "dams_broken"
  | "cases_open"
  | "median_days_to_repair"
  | "tasks_on_time_pct";

export type StatCopy = { label: string; unit: string; hint: string; empty: string };

export type PublicCopy = {
  eyebrow: (week: string) => string;
  title: (region: string) => string;
  freshness: (pass: string, run: string) => string;
  regionLabel: string;
  weekLabel: string;
  latestWeek: string;
  toggleLabel: string;
  stats: Record<StatKey, StatCopy>;
  escalatedHint: (count: number) => string;
  statSource: (field: string, asOf: string) => string;
  rankingOnly: string;
  loading: string;
  failed: string;
  retry: string;
  noRanking: (week: string) => string;
  map: {
    label: string;
    keyMissing: string;
    layers: string;
    drying: string;
    burnScars: string;
    reignition: string;
    layerUnavailable: string;
    lowScore: string;
    highScore: string;
    damBroken: string;
    damDamaged: string;
    damIntact: string;
    openCase: string;
    cell: (id: string, score: string) => string;
  };
  record: {
    title: string;
    note: string;
    example: string;
    empty: string;
    failed: string;
    kinds: Record<"opened" | "task" | "overdue" | "escalated" | "closed", string>;
  };
  data: {
    title: string;
    lede: (week: string) => string;
    csv: string;
    geojson: string;
    api: (path: string) => string;
    license: string;
    credits: string;
  };
  bulletin: {
    title: string;
    gemini: string;
    template: string;
    english: string;
    indonesian: string;
    howTitle: string;
    howGemini: string;
    howTemplate: string;
    model: string;
    promptVersion: string;
    citedFields: string;
    writtenAt: string;
    empty: string;
    unavailableRegion: string;
    failed: string;
    fields: Record<string, string>;
  };
};

const EN: PublicCopy = {
  eyebrow: (week) => `Public dashboard · Week ${week}`,
  title: (region) => `${region} peat this week`,
  freshness: (pass, run) => `Satellite pass ${pass} · ranking run ${run}`,
  regionLabel: "Region",
  weekLabel: "Week",
  latestWeek: "Latest week",
  toggleLabel: "Language of this page",
  stats: {
    high_risk_cells: {
      label: "High-risk cells",
      unit: "cells",
      hint: "Drying score 80 or more",
      empty: "No data",
    },
    dams_broken: {
      label: "Dams broken",
      unit: "dams",
      hint: "Broken or damaged, last report",
      empty: "No data",
    },
    cases_open: {
      label: "Open cases",
      unit: "cases",
      hint: "Not yet escalated or closed",
      empty: "No data",
    },
    median_days_to_repair: {
      label: "Days to repair",
      unit: "days",
      hint: "Median, closed dam cases",
      empty: "No repair closed this week",
    },
    tasks_on_time_pct: {
      label: "Tasks on time",
      unit: "%",
      hint: "Done before the deadline",
      empty: "No task was due yet this week",
    },
  },
  escalatedHint: (count) => `${count} escalated to the brigade`,
  statSource: (field, asOf) => `Source: ${field}, data as of ${asOf}`,
  rankingOnly:
    "For Congo this page shows the drying ranking only. Field cases, dams and the response record start in Riau.",
  loading: "Loading this week",
  failed: "Could not load this week.",
  retry: "Try again",
  noRanking: (week) => `There is no ranking for ${week} yet. Choose another week.`,
  map: {
    label: "Map of drying cells and dams",
    keyMissing: "The map is not available right now.",
    layers: "Map layers",
    drying: "Drying score",
    burnScars: "Burn scars",
    reignition: "Re-ignition risk",
    layerUnavailable: "not ready",
    lowScore: "0 low",
    highScore: "100 high",
    damBroken: "Dam broken",
    damDamaged: "Dam damaged",
    damIntact: "Dam intact",
    openCase: "Open case",
    cell: (id, score) => `Cell ${id}, drying score ${score}`,
  },
  record: {
    title: "Response record",
    note: "Written from the case state and the task, not by Gemini. A cell ID, never a person, a photo or a point.",
    example: "Example data",
    empty: "No cases yet.",
    failed: "Could not load the response record.",
    kinds: {
      opened: "Opened",
      task: "Assigned",
      overdue: "Overdue",
      escalated: "Escalated",
      closed: "Closed",
    },
  },
  data: {
    title: "Open data",
    lede: (week) => `All scored cells for ${week}: score, rank and the numbers behind each score.`,
    csv: "Download CSV",
    geojson: "Download GeoJSON",
    api: (path) => `Public API: ${path}`,
    license:
      "License CC BY-NC-SA 4.0, because the peat map is. Share it, credit it, keep it non-commercial.",
    credits: "Credits",
  },
  bulletin: {
    title: "Weekly bulletin",
    gemini: "Gemini bulletin",
    template: "Template text",
    english: "English",
    indonesian: "Bahasa Indonesia",
    howTitle: "How this was written",
    howGemini:
      "Written by Gemini from this week's public numbers only. Every number is checked against them before it is shown.",
    howTemplate:
      "Gemini did not write this one. This is a fixed template filled with this week's public numbers.",
    model: "Model",
    promptVersion: "Prompt version",
    citedFields: "Cited fields",
    writtenAt: "Written",
    empty: "The bulletin for this week is not written yet.",
    unavailableRegion: "Bulletins cover Riau for now.",
    failed: "Could not load the bulletin.",
    fields: {
      high_risk_cells: "High-risk cells",
      dams_broken: "Dams broken",
      cases_open: "Open cases",
      cases_escalated: "Escalated cases",
      cases_closed: "Closed cases",
      median_days_to_repair: "Days to repair",
      tasks_on_time_pct: "Tasks on time (%)",
    },
  },
};

const ID: PublicCopy = {
  eyebrow: (week) => `Dasbor publik · Minggu ${week}`,
  title: (region) => `Gambut ${region} minggu ini`,
  freshness: (pass, run) => `Lintasan satelit ${pass} · peringkat dihitung ${run}`,
  regionLabel: "Wilayah",
  weekLabel: "Minggu",
  latestWeek: "Minggu terbaru",
  toggleLabel: "Bahasa halaman ini",
  stats: {
    high_risk_cells: {
      label: "Petak berisiko tinggi",
      unit: "petak",
      hint: "Skor pengeringan 80 atau lebih",
      empty: "Belum ada data",
    },
    dams_broken: {
      label: "Sekat kanal rusak",
      unit: "sekat",
      hint: "Rusak atau jebol, laporan terakhir",
      empty: "Belum ada data",
    },
    cases_open: {
      label: "Kasus terbuka",
      unit: "kasus",
      hint: "Belum diteruskan atau ditutup",
      empty: "Belum ada data",
    },
    median_days_to_repair: {
      label: "Hari perbaikan",
      unit: "hari",
      hint: "Median, kasus sekat yang ditutup",
      empty: "Belum ada perbaikan selesai minggu ini",
    },
    tasks_on_time_pct: {
      label: "Tugas tepat waktu",
      unit: "%",
      hint: "Selesai sebelum tenggat",
      empty: "Belum ada tugas yang jatuh tempo minggu ini",
    },
  },
  escalatedHint: (count) => `${count} diteruskan ke pemadam`,
  statSource: (field, asOf) => `Sumber: ${field}, data per ${asOf}`,
  rankingOnly:
    "Untuk Kongo, halaman ini hanya menampilkan peringkat pengeringan. Kasus lapangan, sekat kanal, dan catatan respons baru ada di Riau.",
  loading: "Memuat minggu ini",
  failed: "Minggu ini belum bisa dimuat.",
  retry: "Coba lagi",
  noRanking: (week) => `Belum ada peringkat untuk ${week}. Pilih minggu lain.`,
  map: {
    label: "Peta petak kering dan sekat kanal",
    keyMissing: "Peta belum bisa ditampilkan sekarang.",
    layers: "Lapisan peta",
    drying: "Skor pengeringan",
    burnScars: "Bekas terbakar",
    reignition: "Risiko menyala lagi",
    layerUnavailable: "belum siap",
    lowScore: "0 rendah",
    highScore: "100 tinggi",
    damBroken: "Sekat jebol",
    damDamaged: "Sekat rusak",
    damIntact: "Sekat utuh",
    openCase: "Kasus terbuka",
    cell: (id, score) => `Petak ${id}, skor pengeringan ${score}`,
  },
  record: {
    title: "Catatan respons",
    note: "Disusun dari status kasus dan tugasnya, bukan oleh Gemini. Hanya ID petak, tidak pernah orang, foto, atau titik lokasi.",
    example: "Data contoh",
    empty: "Belum ada kasus.",
    failed: "Catatan respons belum bisa dimuat.",
    kinds: {
      opened: "Dibuka",
      task: "Ditugaskan",
      overdue: "Terlambat",
      escalated: "Diteruskan",
      closed: "Ditutup",
    },
  },
  data: {
    title: "Data terbuka",
    lede: (week) =>
      `Semua petak yang dinilai untuk ${week}: skor, peringkat, dan angka di balik tiap skor.`,
    csv: "Unduh CSV",
    geojson: "Unduh GeoJSON",
    api: (path) => `API publik: ${path}`,
    license:
      "Lisensi CC BY-NC-SA 4.0, mengikuti peta gambutnya. Boleh dibagikan dengan menyebut sumber, tanpa tujuan komersial.",
    credits: "Sumber data",
  },
  bulletin: {
    title: "Buletin mingguan",
    gemini: "Buletin Gemini",
    template: "Teks templat",
    english: "English",
    indonesian: "Bahasa Indonesia",
    howTitle: "Cara buletin ini ditulis",
    howGemini:
      "Ditulis Gemini hanya dari angka publik minggu ini. Setiap angka dicocokkan dengan data itu sebelum ditampilkan.",
    howTemplate:
      "Bukan Gemini yang menulis ini. Teks ini templat tetap yang diisi angka publik minggu ini.",
    model: "Model",
    promptVersion: "Versi prompt",
    citedFields: "Bidang yang dikutip",
    writtenAt: "Ditulis",
    empty: "Buletin minggu ini belum ditulis.",
    unavailableRegion: "Untuk sekarang buletin hanya untuk Riau.",
    failed: "Buletin belum bisa dimuat.",
    fields: {
      high_risk_cells: "Petak berisiko tinggi",
      dams_broken: "Sekat kanal rusak",
      cases_open: "Kasus terbuka",
      cases_escalated: "Kasus diteruskan",
      cases_closed: "Kasus ditutup",
      median_days_to_repair: "Hari perbaikan",
      tasks_on_time_pct: "Tugas tepat waktu (%)",
    },
  },
};

export function publicCopy(language: CopyLanguage): PublicCopy {
  return language === "id" ? ID : EN;
}
