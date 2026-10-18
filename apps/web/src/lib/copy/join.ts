import type { Language } from "../contracts";
import type { JoinFailure } from "../join/errors";
import type { JoinField } from "../join/form";
import type { CopyLanguage } from "./language";

export type JoinCopy = {
  title: string;
  lede: string;
  checkingSignIn: string;
  signInFailed: string;
  signInTitle: string;
  signInHint: string;
  signInButton: string;
  signingIn: string;
  signInError: string;
  signedInAs: (name: string | null) => string;
  fields: {
    inviteCode: { label: string; hint: string };
    name: { label: string };
    home: { label: string; hint: string };
    language: { label: string };
    whatsapp: { label: string; hint: string };
  };
  languages: Record<Language, string>;
  homeGps: string;
  homeLocating: string;
  homeDenied: string;
  homeUnsupported: string;
  homeUnavailable: string;
  homeDeniedNoMap: string;
  homeMapNote: string;
  homeMapMissing: string;
  homeChosen: (lat: string, lon: string) => string;
  homePaste: string;
  homePasteHint: string;
  homePasteError: string;
  submit: string;
  submitting: string;
  fieldErrors: Record<JoinField, string>;
  failures: Record<JoinFailure, string>;
  toggleLabel: string;
};

const ID: JoinCopy = {
  title: "Gabung sebagai relawan",
  lede: "Bara mengirim tugas cek sekat kanal ke relawan di dekat lokasi. Isi data di bawah untuk mulai.",
  checkingSignIn: "Memeriksa akun Anda",
  signInFailed: "Akun tidak bisa diperiksa. Muat ulang halaman, lalu coba lagi.",
  signInTitle: "Masuk dulu",
  signInHint: "Gunakan akun Google Anda. Kode undangan diisi setelah masuk.",
  signInButton: "Masuk dengan Google",
  signingIn: "Membuka Google",
  signInError: "Gagal masuk dengan Google. Coba lagi.",
  signedInAs: (name) => (name === null ? "Anda sudah masuk." : `Masuk sebagai ${name}.`),
  fields: {
    inviteCode: { label: "Kode undangan", hint: "Kode dari tim Bara." },
    name: { label: "Nama" },
    home: { label: "Lokasi rumah", hint: "Dipakai untuk memilih tugas yang dekat dengan Anda." },
    language: { label: "Bahasa pesan" },
    whatsapp: {
      label: "Nomor WhatsApp (boleh kosong)",
      hint: "Awali dengan kode negara, misalnya +62.",
    },
  },
  languages: { id: "Bahasa Indonesia", en: "English", ms: "Bahasa Melayu", fr: "Français" },
  homeGps: "Pakai lokasi saya",
  homeLocating: "Mencari lokasi",
  homeDenied: "Lokasi tidak bisa dibaca. Tandai rumah Anda di peta.",
  homeUnsupported: "Perangkat ini tidak bisa membaca lokasi. Tandai rumah Anda di peta.",
  homeUnavailable: "Lokasi belum ditemukan. Coba lagi di tempat yang lebih terbuka.",
  homeDeniedNoMap:
    "Lokasi tidak bisa dibaca. Izinkan lokasi di pengaturan peramban, lalu coba lagi.",
  homeMapNote: "Atau ketuk peta untuk menaruh pin.",
  homeMapMissing: "Peta tidak tersedia. Pakai lokasi saya.",
  homeChosen: (lat, lon) => `Pin terpasang: ${lat}, ${lon}`,
  homePaste: "Tempel koordinat",
  homePasteHint: "Contoh: 0.79990, 102.47081",
  homePasteError: "Tulis lintang, bujur, misalnya 0.79990, 102.47081.",
  submit: "Gabung",
  submitting: "Mengirim",
  fieldErrors: {
    inviteCode: "Isi kode undangan.",
    name: "Isi nama Anda, paling banyak 80 huruf.",
    home: "Pilih lokasi rumah.",
    whatsapp: "Tulis nomor dengan kode negara, misalnya +6281234567890.",
  },
  failures: {
    wrong_code: "Kode undangan salah. Periksa kodenya, lalu coba lagi.",
    already_has_role:
      "Akun ini sudah punya peran di Bara (ops, brigade, atau Panel Demo), jadi tidak bisa gabung sebagai relawan. Pakai akun lain.",
    too_many_attempts: "Terlalu banyak percobaan. Tunggu sebentar, lalu coba lagi.",
    not_signed_in: "Masuk dengan Google dulu, lalu kirim lagi.",
    unavailable: "Layanan gabung sedang tidak bisa dipakai. Coba lagi sebentar lagi.",
    network: "Tidak ada sinyal. Data Anda masih di formulir, coba kirim lagi.",
    unknown: "Gabung gagal. Data Anda masih di formulir, coba lagi.",
  },
  toggleLabel: "Bahasa tampilan",
};

const EN: JoinCopy = {
  title: "Join as a volunteer",
  lede: "Bara sends canal dam checks to volunteers near the site. Fill in the form to start.",
  checkingSignIn: "Checking your account",
  signInFailed: "Could not check your account. Reload the page and try again.",
  signInTitle: "Sign in first",
  signInHint: "Use your Google account. You enter the invite code after you sign in.",
  signInButton: "Sign in with Google",
  signingIn: "Opening Google",
  signInError: "Google sign-in failed. Try again.",
  signedInAs: (name) => (name === null ? "You are signed in." : `Signed in as ${name}.`),
  fields: {
    inviteCode: { label: "Invite code", hint: "The code from the Bara team." },
    name: { label: "Name" },
    home: { label: "Home location", hint: "Used to pick tasks near you." },
    language: { label: "Message language" },
    whatsapp: {
      label: "WhatsApp number (optional)",
      hint: "Start with the country code, for example +62.",
    },
  },
  languages: { id: "Bahasa Indonesia", en: "English", ms: "Bahasa Melayu", fr: "Français" },
  homeGps: "Use my location",
  homeLocating: "Finding your location",
  homeDenied: "Could not read your location. Drop a pin on the map.",
  homeUnsupported: "This device cannot read a location. Drop a pin on the map.",
  homeUnavailable: "Your location was not found. Try again somewhere more open.",
  homeDeniedNoMap:
    "Could not read your location. Allow location in the browser settings, then try again.",
  homeMapNote: "Or tap the map to drop a pin.",
  homeMapMissing: "The map is not available. Use my location.",
  homeChosen: (lat, lon) => `Pin set: ${lat}, ${lon}`,
  homePaste: "Paste coordinates",
  homePasteHint: "Example: 0.79990, 102.47081",
  homePasteError: "Write latitude, longitude, for example 0.79990, 102.47081.",
  submit: "Join",
  submitting: "Sending",
  fieldErrors: {
    inviteCode: "Enter the invite code.",
    name: "Enter your name, 80 characters at most.",
    home: "Choose your home location.",
    whatsapp: "Write the number with the country code, for example +6281234567890.",
  },
  failures: {
    wrong_code: "The invite code is wrong. Check it and try again.",
    already_has_role:
      "This account already has a role in Bara (ops, brigade or Demo Panel), so it cannot join as a volunteer. Use another account.",
    too_many_attempts: "Too many tries. Wait a moment, then try again.",
    not_signed_in: "Sign in with Google first, then send again.",
    unavailable: "Joining is not available right now. Try again in a moment.",
    network: "No signal. Your answers are still in the form, try sending again.",
    unknown: "Joining failed. Your answers are still in the form, try again.",
  },
  toggleLabel: "Display language",
};

export function joinCopy(language: CopyLanguage): JoinCopy {
  return language === "en" ? EN : ID;
}
