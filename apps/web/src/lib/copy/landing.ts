import type { CopyLanguage } from "./language";

export type LandingMoment = { when: string; body: string };

export type DamDiagramCopy = {
  works: string;
  broken: string;
  canal: string;
  dam: string;
  wetPeat: string;
  dryPeat: string;
  waterLine: string;
  smoulder: string;
  radarNote: string;
};

export type LandingCopy = {
  toggleLabel: string;
  title: string;
  tourNote: string;
  startTour: string;
  resumeTour: (step: number, total: number) => string;
  explore: string;
  problem: {
    title: string;
    paragraphs: readonly string[];
    diagram: DamDiagramCopy;
  };
  solution: {
    title: string;
    before: LandingMoment;
    after: LandingMoment;
  };
  why: {
    title: string;
    paragraphs: readonly string[];
  };
  closing: {
    title: string;
    body: string;
    tour: string;
    publicPage: string;
  };
  team: string;
};

const EN: LandingCopy = {
  toggleLabel: "Language of this page",
  title: "Bara finds peat that is drying faster than normal and sends a person to check.",
  tourNote: "The guided tour takes under 5 minutes and runs on the live system.",
  startTour: "Start the guided tour",
  resumeTour: (step, total) => `Resume at step ${step} of ${total}`,
  explore: "Explore freely",
  problem: {
    title: "Why drying peat is a fire risk",
    paragraphs: [
      "Peat is hard to burn while its water stays near the surface. Canals drain it, for farms and plantations, and when the water drops too far or a dam breaks, the top layer dries into fuel.",
      "Satellites already see the peat drying, but a map does not send anyone to check. A fire that looks out can also keep burning underground and come back days later.",
    ],
    diagram: {
      works: "Dam works: water stays high, peat stays moist",
      broken: "Dam broken: water drains away, top peat dries",
      canal: "canal",
      dam: "dam",
      wetPeat: "moist peat",
      dryPeat: "dry peat: fuel",
      waterLine: "water line",
      smoulder: "fire can smoulder here",
      radarNote: "Bara sees the drop in the water line as drying in radar data.",
    },
  },
  solution: {
    title: "What Bara does",
    before: {
      when: "Before the dry season",
      body: "Bara ranks peat areas each week by how fast they are drying, drained land included, and sends a named person to check the area or its dam. Checking early gives teams time to act.",
    },
    after: {
      when: "After a fire looks out",
      body: "Bara scores where burned peat may burn again and sends a patrol back to check. Smoke in a photo, or no answer by the deadline, goes to the fire brigade.",
    },
  },
  why: {
    title: "Why we built it",
    paragraphs: [
      "The signs of a peat fire show early: the peat dries before anything burns. What was missing is the step from that signal to a person who can check.",
      "Bara is that step. It names who checks, asks for proof, and escalates to the fire brigade when there is smoke or a check is overdue. It is tested on data, not yet in the field.",
    ],
  },
  closing: {
    title: "See it work",
    body: "Run the guided tour on the live system, or open the public page.",
    tour: "Take the tour",
    publicPage: "Open the public page",
  },
  team: "Bara is built by team Faber Fathers for Google Cloud AI Builder Cup 2026: Rizqy EP, Rama Dhaniansyah, Rafizhafran Halmi and Ramel Akil Pratama.",
};

const ID: LandingCopy = {
  toggleLabel: "Bahasa halaman ini",
  title:
    "Bara menemukan gambut yang mengering lebih cepat dari biasanya, lalu mengirim orang untuk mengeceknya.",
  tourNote:
    "Tur terpandu selesai dalam kurang dari 5 menit, langsung di sistem yang sedang berjalan. Tur ini berbahasa Inggris.",
  startTour: "Mulai tur terpandu",
  resumeTour: (step, total) => `Lanjutkan di langkah ${step} dari ${total}`,
  explore: "Jelajahi sendiri",
  problem: {
    title: "Kenapa gambut yang mengering berisiko terbakar",
    paragraphs: [
      "Gambut sulit terbakar selama airnya tetap dekat permukaan. Kanal menguras air itu, misalnya untuk kebun dan perkebunan. Kalau muka air turun terlalu jauh atau sekat kanal jebol, lapisan atasnya mengering dan jadi bahan bakar.",
      "Satelit sudah bisa melihat gambut mengering, tapi peta tidak mengirim siapa pun untuk mengecek. Api yang tampak padam juga bisa terus membara di bawah tanah dan menyala lagi beberapa hari kemudian.",
    ],
    diagram: {
      works: "Sekat utuh: air tetap tinggi, gambut tetap lembap",
      broken: "Sekat jebol: air mengalir keluar, gambut bagian atas mengering",
      canal: "kanal",
      dam: "sekat",
      wetPeat: "gambut lembap",
      dryPeat: "gambut kering: bahan bakar",
      waterLine: "muka air",
      smoulder: "api bisa membara di sini",
      radarNote: "Bara melihat turunnya muka air ini sebagai tanda mengering di data radar.",
    },
  },
  solution: {
    title: "Yang dilakukan Bara",
    before: {
      when: "Sebelum kemarau",
      body: "Tiap minggu Bara mengurutkan area gambut menurut kecepatan keringnya, termasuk lahan yang dikeringkan, lalu menugaskan satu orang untuk mengecek area atau sekatnya. Pengecekan sejak dini memberi tim waktu untuk bertindak.",
    },
    after: {
      when: "Setelah api tampak padam",
      body: "Bara menilai bagian bekas terbakar yang bisa menyala lagi, lalu mengirim patroli untuk mengecek. Kalau foto menunjukkan asap, atau tidak ada jawaban sampai batas waktu, kasusnya diteruskan ke regu pemadam.",
    },
  },
  why: {
    title: "Kenapa kami membuatnya",
    paragraphs: [
      "Tanda-tanda kebakaran gambut muncul lebih awal: gambut mengering sebelum ada yang terbakar. Yang belum ada adalah jembatan dari tanda itu ke orang yang bisa mengecek.",
      "Bara menjadi jembatan itu. Ia menunjuk siapa yang mengecek, meminta bukti, dan meneruskan ke regu pemadam kalau ada asap atau pengecekan terlambat. Bara baru diuji dengan data, belum di lapangan.",
    ],
  },
  closing: {
    title: "Coba sendiri",
    body: "Jalankan tur terpandu di sistem yang sedang berjalan, atau buka halaman publik.",
    tour: "Ikuti tur",
    publicPage: "Buka halaman publik",
  },
  team: "Bara dibuat oleh tim Faber Fathers untuk Google Cloud AI Builder Cup 2026: Rizqy EP, Rama Dhaniansyah, Rafizhafran Halmi, dan Ramel Akil Pratama.",
};

const COPY: Record<CopyLanguage, LandingCopy> = { en: EN, id: ID };

export function landingCopy(language: CopyLanguage): LandingCopy {
  return COPY[language];
}
