import type { AreaErrorKind } from "../area/errors";
import type { CopyLanguage } from "./language";
import type { SamplePickerCopy } from "./samples";

export type AreaCopy = SamplePickerCopy & {
  title: string;
  lede: string;
  sampleChip: string;
  loadedTitle: string;
  vertices: (count: number) => string;
  credit: (credit: string) => string;
  loadFailed: string;
  toggleLabel: string;
  drawHint: string;
  drawn: (corners: number, km2: number) => string;
  undo: string;
  clear: string;
  rank: string;
  tooFew: string;
  tooLarge: (limit: number) => string;
  ranking: (seconds: number) => string;
  resultTitle: (week: string) => string;
  resultMeta: (peatCells: number, km2: number) => string;
  cachedNote: string;
  cellScore: (rank: number, id: string, score: number) => string;
  noPeat: string;
  mapKeyMissing: string;
  errors: Record<AreaErrorKind, string>;
};

const ID: AreaCopy = {
  title: "Gambar area",
  lede: "Gambar area di peta, lalu minta peringkat pengeringannya. Atau pilih contoh.",
  useSample: "Pakai contoh",
  sampleTitle: "Pilih contoh area",
  sampleLoading: "Memuat contoh",
  sampleEmpty: "Belum ada contoh area.",
  sampleFailed: "Contoh tidak termuat. Coba lagi.",
  retry: "Coba lagi",
  sampleChip: "Sampel",
  loadedTitle: "Area terpilih",
  vertices: (count) => `${count} titik sudut`,
  credit: (credit) => `Sumber: ${credit}`,
  loadFailed: "Berkas area ini tidak bisa dibaca. Pilih contoh lain.",
  toggleLabel: "Bahasa tampilan",
  drawHint: "Ketuk peta untuk menaruh titik sudut. Butuh minimal 3 titik.",
  drawn: (corners, km2) => `${corners} titik sudut, sekitar ${km2} km²`,
  undo: "Hapus titik terakhir",
  clear: "Hapus semua",
  rank: "Peringkatkan area ini",
  tooFew: "Taruh minimal 3 titik sudut.",
  tooLarge: (limit) => `Area terlalu luas. Batasnya ${limit} km².`,
  ranking: (seconds) => `Menghitung peringkat, ${seconds} dtk. Bisa sampai 60 dtk.`,
  resultTitle: (week) => `Sel terkering minggu ${week}`,
  resultMeta: (peatCells, km2) => `${peatCells} sel gambut di area ${km2} km²`,
  cachedNote: "Hasil tersimpan dari permintaan yang sama.",
  cellScore: (rank, id, score) => `${rank}. ${id}, skor ${score}`,
  noPeat: "Tidak ada gambut terpetakan di area ini. Geser atau perluas area.",
  mapKeyMissing: "Kunci peta belum diisi, jadi peta tidak tampil.",
  errors: {
    limit: "Batas 10 peringkat per jam sudah terpakai. Coba lagi nanti.",
    too_large: "Area terlalu luas. Kecilkan sampai 2.500 km².",
    outside: "Area ini di luar wilayah yang kami pantau. Gambar di sekitar Riau.",
    invalid: "Bentuk area tidak sah. Garis tidak boleh saling silang.",
    busy: "Server sedang sibuk menghitung. Coba lagi sebentar lagi.",
    timeout: "Perhitungan melewati 60 detik. Coba area yang lebih kecil.",
    failed: "Peringkat area gagal dihitung. Coba lagi.",
  },
};

const EN: AreaCopy = {
  title: "Draw an area",
  lede: "Pick a small sample area in Riau to try the flow.",
  useSample: "Use a sample",
  sampleTitle: "Choose a sample area",
  sampleLoading: "Loading samples",
  sampleEmpty: "No sample areas yet.",
  sampleFailed: "The samples did not load. Try again.",
  retry: "Try again",
  sampleChip: "Sample",
  loadedTitle: "Chosen area",
  vertices: (count) => `${count} corners`,
  credit: (credit) => `Source: ${credit}`,
  loadFailed: "This area file could not be read. Choose another sample.",
  toggleLabel: "Display language",
  drawHint: "Tap the map to place corners. You need at least 3.",
  drawn: (corners, km2) => `${corners} corners, about ${km2} km²`,
  undo: "Remove last corner",
  clear: "Clear all",
  rank: "Rank this area",
  tooFew: "Place at least 3 corners.",
  tooLarge: (limit) => `The area is too large. The limit is ${limit} km².`,
  ranking: (seconds) => `Ranking, ${seconds} s. It can take up to 60 s.`,
  resultTitle: (week) => `Driest cells, week ${week}`,
  resultMeta: (peatCells, km2) => `${peatCells} peat cells in ${km2} km²`,
  cachedNote: "Saved result from the same request.",
  cellScore: (rank, id, score) => `${rank}. ${id}, score ${score}`,
  noPeat: "No mapped peat in this area. Move it or make it larger.",
  mapKeyMissing: "The map key is not set, so the map does not show.",
  errors: {
    limit: "You used all 10 rankings for this hour. Try again later.",
    too_large: "The area is too large. Shrink it to 2,500 km².",
    outside: "This area is outside the regions we watch. Draw near Riau.",
    invalid: "The shape is not valid. Its lines must not cross.",
    busy: "The server is busy ranking. Try again in a moment.",
    timeout: "The ranking took longer than 60 s. Try a smaller area.",
    failed: "The area could not be ranked. Try again.",
  },
};

export function areaCopy(language: CopyLanguage): AreaCopy {
  return language === "en" ? EN : ID;
}
