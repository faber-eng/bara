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
  rankingSoon: string;
  toggleLabel: string;
};

const ID: AreaCopy = {
  title: "Gambar area",
  lede: "Pilih contoh area kecil di Riau untuk mencoba alurnya.",
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
  rankingSoon: "Peringkat area belum tersedia di versi ini.",
  toggleLabel: "Bahasa tampilan",
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
  rankingSoon: "Ranking an area is not available in this version yet.",
  toggleLabel: "Display language",
};

export function areaCopy(language: CopyLanguage): AreaCopy {
  return language === "en" ? EN : ID;
}
