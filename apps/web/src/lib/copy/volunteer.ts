import type { DamState, HotGround, Smoke, TaskType } from "../contracts";
import type { PickKind } from "../volunteer/evidenceKinds";
import type { CopyLanguage } from "./language";

export type HeadlineKey =
  | "location_mismatch"
  | "smoke"
  | "dam_broken"
  | "dam_damaged"
  | "dam_intact"
  | "dam_overtopped"
  | "unclear"
  | "received";

export type NextKey = "human" | "location" | "forwarded" | "recorded" | "stay_away";

export type VolunteerCopy = {
  loading: string;
  loadFailed: string;
  retry: string;
  notYours: string;
  emptyTitle: string;
  emptyBody: string;
  taskTitles: Record<TaskType, string>;
  whatToSend: Record<TaskType, string>;
  deadline: (when: string) => string;
  overdue: string;
  openMap: string;
  doneChip: string;
  takePhoto: string;
  photoFile: string;
  recordVoice: string;
  useSample: string;
  stopRecording: string;
  recording: string;
  recordingHint: string;
  micDenied: string;
  cameraHint: string;
  sampleChip: string;
  sampleTitle: string;
  sampleLoading: string;
  sampleEmpty: string;
  sampleFailed: string;
  previewAlt: string;
  previewNote: string;
  sendPhoto: string;
  retake: string;
  back: string;
  uploadingPhoto: string;
  uploadingVoice: string;
  keepOpen: string;
  readingTitle: string;
  readingNote: string;
  readingSlow: string;
  queuedTitle: string;
  queuedNote: string;
  outboxWaiting: (count: number) => string;
  outboxSendNow: string;
  recordVideo: string;
  videoFile: string;
  uploadingVideo: string;
  videoTooLong: string;
  videoTooBig: string;
  videoType: string;
  uploadFailed: string;
  readFailed: string;
  prepareFailed: string;
  tryAgain: string;
  sendAnother: string;
  progressLabel: string;
  geminiChip: string;
  headline: Record<HeadlineKey, string>;
  next: Record<NextKey, string>;
  rowDam: string;
  rowSmoke: string;
  rowHot: string;
  rowLocation: string;
  rowConfidence: string;
  rowHeard: string;
  locationOk: string;
  locationBad: string;
  why: string;
  needsHumanChip: string;
  damStates: Record<DamState, string>;
  smokes: Record<Smoke, string>;
  hotGrounds: Record<HotGround, string>;
  chatPlaceholder: string;
  chatSend: string;
  chatFailed: string;
  chatFrom: string;
  chatYou: string;
  chatSending: string;
  chatReplying: string;
  newMessage: string;
  toggleLabel: string;
  threadLabel: string;
  tasksLabel: string;
  captureLabel: string;
  evidenceRowLabel: string;
  kindLabels: Record<PickKind, string>;
  kindSent: (label: string) => string;
  addDialogTitle: Record<PickKind, string>;
  cancel: string;
};

const ID: VolunteerCopy = {
  loading: "Memuat tugas Anda",
  loadFailed: "Tugas tidak termuat. Periksa sinyal Anda, lalu coba lagi.",
  retry: "Coba lagi",
  notYours: "Halaman ini milik relawan lain. Buka halaman Anda sendiri setelah masuk.",
  emptyTitle: "Belum ada tugas",
  emptyBody: "Bara akan mengirim tugas di sini saat ada sekat atau lahan yang perlu dicek.",
  taskTitles: {
    dam_check: "Cek sekat kanal",
    dam_repair: "Perbaiki sekat kanal",
    patrol_recheck: "Cek ulang lahan bekas terbakar",
  },
  whatToSend: {
    dam_check: "1 foto sekat, 1 pesan suara",
    dam_repair: "1 foto setelah perbaikan",
    patrol_recheck: "1 foto lahan, 1 pesan suara jika ada asap",
  },
  deadline: (when) => `Sebelum ${when}`,
  overdue: "Lewat batas",
  openMap: "Buka di peta",
  doneChip: "Selesai",
  takePhoto: "Ambil foto",
  photoFile: "Berkas foto",
  recordVoice: "Rekam pesan suara",
  useSample: "Pakai contoh",
  stopRecording: "Berhenti merekam",
  recording: "Merekam pesan suara",
  recordingHint: "Ceritakan kondisi sekat dengan kata-kata Anda.",
  micDenied:
    "Mikrofon tidak bisa dipakai. Izinkan mikrofon di pengaturan peramban, lalu coba lagi.",
  cameraHint: "Foto dikecilkan ke 1600 px sebelum dikirim, supaya cepat di sinyal lemah.",
  sampleChip: "Sampel",
  sampleTitle: "Pilih contoh",
  sampleLoading: "Memuat contoh",
  sampleEmpty: "Belum ada contoh untuk jenis ini.",
  sampleFailed: "Contoh tidak termuat. Coba lagi.",
  previewAlt: "Pratinjau foto yang akan dikirim.",
  previewNote: "Diperkecil ke 1600 px, JPEG kualitas 0,8.",
  sendPhoto: "Kirim foto",
  retake: "Ambil ulang",
  back: "Kembali",
  uploadingPhoto: "Mengirim foto",
  uploadingVoice: "Mengirim pesan suara",
  keepOpen: "Jangan tutup halaman ini.",
  readingTitle: "Gemini sedang membaca kiriman Anda",
  readingNote: "Biasanya kurang dari 10 detik.",
  queuedTitle: "Tersimpan di ponsel",
  queuedNote: "Tidak ada sinyal. Kiriman Anda akan terkirim sendiri begitu sinyal kembali.",
  outboxWaiting: (count) => `${count} kiriman menunggu sinyal`,
  outboxSendNow: "Kirim sekarang",
  recordVideo: "Rekam video",
  videoFile: "Berkas video",
  uploadingVideo: "Mengirim video",
  videoTooLong: "Video lebih dari 30 detik. Rekam ulang yang lebih singkat.",
  videoTooBig:
    "Video terlalu besar (maksimal 25 MB). Rekam ulang yang lebih singkat atau pada resolusi lebih rendah.",
  videoType: "Video harus berformat MP4 atau MOV.",
  readingSlow: "Hasil belum keluar. Kiriman Anda sudah diterima, cek lagi sebentar lagi.",
  uploadFailed: "Kiriman gagal terkirim. Periksa sinyal Anda, lalu coba lagi.",
  readFailed: "Kiriman diterima, tetapi hasilnya belum bisa dimuat.",
  prepareFailed: "Berkas ini tidak bisa disiapkan. Pilih berkas lain.",
  tryAgain: "Kirim lagi",
  sendAnother: "Kirim yang lain",
  progressLabel: "Kemajuan kirim",
  geminiChip: "Gemini",
  headline: {
    location_mismatch: "Lokasi foto tidak cocok",
    smoke: "Terlihat asap",
    dam_broken: "Sekat terlihat jebol",
    dam_damaged: "Sekat terlihat rusak",
    dam_intact: "Sekat terlihat utuh",
    dam_overtopped: "Air meluap di atas sekat",
    unclear: "Kiriman kurang jelas",
    received: "Kiriman diterima",
  },
  next: {
    human: "Seorang petugas akan memeriksa ini. Anda tidak perlu mengirim ulang.",
    location:
      "Seorang petugas akan memeriksa. Jika Anda salah titik, buka peta tugas dan kirim lagi.",
    forwarded: "Bara meneruskan temuan ini untuk ditindaklanjuti. Terima kasih.",
    recorded: "Temuan Anda sudah tercatat. Terima kasih.",
    stay_away: "Tetap jauhi lahan itu. Temuan Anda diteruskan. Terima kasih.",
  },
  rowDam: "Kondisi sekat",
  rowSmoke: "Asap",
  rowHot: "Tanda tanah panas",
  rowLocation: "Lokasi",
  rowConfidence: "Keyakinan",
  rowHeard: "Yang terdengar",
  locationOk: "Cocok",
  locationBad: "Tidak cocok",
  why: "Kenapa?",
  needsHumanChip: "Perlu ditinjau orang",
  damStates: {
    intact: "Utuh",
    damaged: "Rusak",
    broken: "Jebol",
    overtopped: "Meluap",
    not_applicable: "Bukan sekat",
    unknown: "Belum diketahui",
  },
  smokes: { none: "Tidak ada", wisps: "Tipis", plume: "Tebal", unknown: "Belum diketahui" },
  hotGrounds: {
    none: "Tidak ada",
    possible: "Mungkin",
    clear: "Jelas",
    unknown: "Belum diketahui",
  },
  chatPlaceholder: "Tulis pesan ke Bara",
  chatSend: "Kirim",
  chatFailed: "Pesan belum terkirim. Coba lagi.",
  chatFrom: "Bara",
  chatYou: "Anda",
  chatSending: "Mengirim pesan",
  chatReplying: "Bara sedang menulis balasan",
  newMessage: "Pesan baru",
  toggleLabel: "Bahasa tampilan",
  threadLabel: "Percakapan dengan Bara",
  tasksLabel: "Tugas Anda",
  captureLabel: "Kirim bukti",
  evidenceRowLabel: "Tambah bukti",
  kindLabels: { photo: "Foto", voice: "Suara", video: "Video" },
  kindSent: (label) => `${label}, terkirim`,
  addDialogTitle: {
    photo: "Tambah foto",
    voice: "Tambah pesan suara",
    video: "Tambah video",
  },
  cancel: "Batal",
};

const EN: VolunteerCopy = {
  loading: "Loading your tasks",
  loadFailed: "Your tasks did not load. Check your signal and try again.",
  retry: "Try again",
  notYours: "This page belongs to another volunteer. Open your own page after you sign in.",
  emptyTitle: "No tasks yet",
  emptyBody: "Bara will send a task here when a dam or a patch of land needs a check.",
  taskTitles: {
    dam_check: "Check the canal dam",
    dam_repair: "Repair the canal dam",
    patrol_recheck: "Recheck the burned land",
  },
  whatToSend: {
    dam_check: "1 dam photo, 1 voice note",
    dam_repair: "1 photo after the repair",
    patrol_recheck: "1 photo of the land, 1 voice note if there is smoke",
  },
  deadline: (when) => `Before ${when}`,
  overdue: "Past the deadline",
  openMap: "Open in maps",
  doneChip: "Done",
  takePhoto: "Take photo",
  photoFile: "Photo file",
  recordVoice: "Record voice note",
  useSample: "Use a sample",
  stopRecording: "Stop recording",
  recording: "Recording a voice note",
  recordingHint: "Describe the dam in your own words.",
  micDenied: "The microphone is not available. Allow it in the browser settings, then try again.",
  cameraHint: "The photo is resized to 1600 px before it is sent, so it is quick on a weak signal.",
  sampleChip: "Sample",
  sampleTitle: "Choose a sample",
  sampleLoading: "Loading samples",
  sampleEmpty: "No samples for this type yet.",
  sampleFailed: "The samples did not load. Try again.",
  previewAlt: "Preview of the photo you are about to send.",
  previewNote: "Resized to 1600 px, JPEG quality 0.8.",
  sendPhoto: "Send photo",
  retake: "Retake",
  back: "Back",
  uploadingPhoto: "Sending photo",
  uploadingVoice: "Sending voice note",
  keepOpen: "Keep this page open.",
  readingTitle: "Gemini is reading what you sent",
  readingNote: "Usually under 10 seconds.",
  queuedTitle: "Saved on your phone",
  queuedNote: "There is no signal. Your upload will send itself when the signal returns.",
  outboxWaiting: (count) =>
    `${count} ${count === 1 ? "upload is" : "uploads are"} waiting for signal`,
  outboxSendNow: "Send now",
  recordVideo: "Record video",
  videoFile: "Video file",
  uploadingVideo: "Sending video",
  videoTooLong: "The video is longer than 30 seconds. Record a shorter one.",
  videoTooBig:
    "The video is too big (25 MB at most). Record a shorter one or at a lower resolution.",
  videoType: "The video must be MP4 or MOV.",
  readingSlow: "The result is not ready. Your upload arrived, check again in a moment.",
  uploadFailed: "The upload did not go through. Check your signal and try again.",
  readFailed: "Your upload arrived, but the result could not be loaded.",
  prepareFailed: "This file could not be prepared. Choose another file.",
  tryAgain: "Send again",
  sendAnother: "Send another",
  progressLabel: "Upload progress",
  geminiChip: "Gemini",
  headline: {
    location_mismatch: "The photo location does not match",
    smoke: "Smoke seen",
    dam_broken: "The dam looks broken",
    dam_damaged: "The dam looks damaged",
    dam_intact: "The dam looks intact",
    dam_overtopped: "Water is over the dam",
    unclear: "The upload is not clear enough",
    received: "Upload received",
  },
  next: {
    human: "A person will check this. You do not need to send it again.",
    location:
      "A person will check. If you picked the wrong spot, open the task map and send again.",
    forwarded: "Bara is passing this finding on for follow-up. Thank you.",
    recorded: "Your finding is recorded. Thank you.",
    stay_away: "Keep away from the land. Your finding is passed on. Thank you.",
  },
  rowDam: "Dam condition",
  rowSmoke: "Smoke",
  rowHot: "Hot ground signs",
  rowLocation: "Location",
  rowConfidence: "Confidence",
  rowHeard: "What was heard",
  locationOk: "Matches",
  locationBad: "Does not match",
  why: "Why?",
  needsHumanChip: "Needs a person to review",
  damStates: {
    intact: "Intact",
    damaged: "Damaged",
    broken: "Broken",
    overtopped: "Overtopped",
    not_applicable: "Not a dam",
    unknown: "Unknown",
  },
  smokes: { none: "None", wisps: "Light", plume: "Heavy", unknown: "Unknown" },
  hotGrounds: { none: "None", possible: "Possible", clear: "Clear", unknown: "Unknown" },
  chatPlaceholder: "Write to Bara",
  chatSend: "Send",
  chatFailed: "The message was not sent. Try again.",
  chatFrom: "Bara",
  chatYou: "You",
  chatSending: "Sending your message",
  chatReplying: "Bara is writing a reply",
  newMessage: "New message",
  toggleLabel: "Display language",
  threadLabel: "Conversation with Bara",
  tasksLabel: "Your tasks",
  captureLabel: "Send evidence",
  evidenceRowLabel: "Add evidence",
  kindLabels: { photo: "Photo", voice: "Voice", video: "Video" },
  kindSent: (label) => `${label}, sent`,
  addDialogTitle: {
    photo: "Add a photo",
    voice: "Add a voice note",
    video: "Add a video",
  },
  cancel: "Cancel",
};

export function volunteerCopy(language: CopyLanguage): VolunteerCopy {
  return language === "en" ? EN : ID;
}
