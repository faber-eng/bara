import type { TourStepId } from "../tour/steps";
import type { CopyLanguage } from "./language";

export type TourStepCopy = { title: string; body: string };

export type TourCopy = {
  dockLabel: string;
  progress: (step: number, total: number) => string;
  skip: string;
  back: string;
  next: string;
  finish: string;
  clockMoved: string;
  triggerSent: string;
  advanceLabel: (hours: number) => string;
  steps: Record<TourStepId, TourStepCopy>;
};

const EN: TourCopy = {
  dockLabel: "Guided tour",
  progress: (step, total) => `Step ${step} of ${total}`,
  skip: "Skip tour",
  back: "Back",
  next: "Next",
  finish: "Finish",
  clockMoved: "Done. The clock moved.",
  triggerSent: "Done. Wait about 30 seconds for the result, then press Next.",
  advanceLabel: (hours) => `+${hours}h`,
  steps: {
    world: {
      title: "The world, with no sign-in",
      body: "Anyone can open this page. It shows this week's peat risk in Riau, the response record and a written bulletin.",
    },
    ranking: {
      title: "Ops: the ranked areas",
      body: "Use the week slider, then open the number one area. Gemini explains the rank and cites the numbers behind it.",
    },
    assign: {
      title: "Start the weekly ranking",
      body: "This sends the drying.ranked event. An agent opens cases for the top areas and picks people. It takes about 30 seconds.",
    },
    stream: {
      title: "Watch the agent decide",
      body: "Open a case in the list. The drawer streams each agent step as it happens: ranking, facts, people, task.",
    },
    evidence: {
      title: "Volunteer Ari sends evidence",
      body: "You are now Ari on a phone view. Press Photo, then Use a sample to send a broken-dam photo. The verdict appears in seconds.",
    },
    quiet: {
      title: "After the fire",
      body: "A fire has gone quiet. This sends the fire.quiet event. The map shows the burn scar and the areas that may burn again.",
    },
    clock: {
      title: "Move the clock 48 hours",
      body: "The agent planned a patrol recheck in 48 hours. Move the clock and watch cases become overdue and escalate.",
    },
    brigade: {
      title: "The brigade inbox",
      body: "The brigade gets one brief with the photo, the map and the timeline, in Indonesian and English.",
    },
    anywhere: {
      title: "Anywhere in the world",
      body: "Congo ranks with the same method. You can also draw any area and rank it live.",
    },
  },
};

const ID: TourCopy = {
  dockLabel: "Tur terpandu",
  progress: (step, total) => `Langkah ${step} dari ${total}`,
  skip: "Lewati tur",
  back: "Kembali",
  next: "Lanjut",
  finish: "Selesai",
  clockMoved: "Selesai. Jam sudah maju.",
  triggerSent: "Selesai. Tunggu sekitar 30 detik sampai hasilnya muncul, lalu tekan Lanjut.",
  advanceLabel: (hours) => `+${hours} jam`,
  steps: {
    world: {
      title: "Dunia tanpa perlu masuk akun",
      body: "Siapa pun bisa membuka halaman ini. Isinya risiko gambut Riau minggu ini, catatan penanganan, dan satu buletin tertulis.",
    },
    ranking: {
      title: "Ops: peringkat area",
      body: "Geser penggeser minggu, lalu buka area peringkat satu. Gemini menjelaskan peringkatnya dan menyebut angka yang mendasarinya.",
    },
    assign: {
      title: "Mulai peringkat mingguan",
      body: "Ini mengirim event drying.ranked. Agen membuka kasus untuk area teratas dan memilih siapa yang bertugas. Prosesnya sekitar 30 detik.",
    },
    stream: {
      title: "Lihat agen mengambil keputusan",
      body: "Buka satu kasus di daftar. Laci kasus menampilkan tiap langkah agen saat itu terjadi: peringkat, fakta, orang, tugas.",
    },
    evidence: {
      title: "Relawan Ari mengirim bukti",
      body: "Sekarang Anda menjadi Ari di tampilan ponsel. Tekan Ambil foto, lalu Pakai contoh untuk mengirim foto sekat yang jebol. Penilaiannya muncul dalam hitungan detik.",
    },
    quiet: {
      title: "Setelah api",
      body: "Satu kebakaran sudah mereda. Ini mengirim event fire.quiet. Peta menampilkan bekas terbakar dan area yang bisa terbakar lagi.",
    },
    clock: {
      title: "Majukan jam 48 jam",
      body: "Agen menjadwalkan pengecekan ulang patroli 48 jam lagi. Majukan jam, lalu lihat kasus lewat tenggat dan naik ke tingkat berikutnya.",
    },
    brigade: {
      title: "Kotak masuk brigade",
      body: "Brigade menerima satu brief berisi foto, peta, dan lini masa, dalam bahasa Indonesia dan Inggris.",
    },
    anywhere: {
      title: "Di mana pun di dunia",
      body: "Kongo diberi peringkat dengan metode yang sama. Anda juga bisa menggambar area apa saja dan memeringkatnya langsung.",
    },
  },
};

export function tourCopy(language: CopyLanguage): TourCopy {
  return language === "id" ? ID : EN;
}
