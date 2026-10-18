import type { CopyLanguage } from "./language";

export type LandingPoint = { title: string; body: string };

export type LandingMoment = {
  when: string;
  signal: string;
  action: string;
  body: string;
};

export type LandingStep = { title: string; ai: string; people: string };

export type LandingPlace = { name: string; body: string };

export type LandingEntryPath = "/public" | "/ops" | "/area/new" | "/join";

export type LandingEntry = { to: LandingEntryPath; label: string; note: string };

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

export type ReignitionLineInput = {
  modelAuc: string;
  baselineAuc: string;
  positives: string;
  events: string;
};

export type LandingCopy = {
  toggleLabel: string;
  title: string;
  audience: string;
  tourNote: string;
  startTour: string;
  resumeTour: (step: number, total: number) => string;
  explore: string;
  problem: {
    title: string;
    points: readonly LandingPoint[];
    stakes: string;
    diagram: DamDiagramCopy;
  };
  moments: {
    title: string;
    before: LandingMoment;
    after: LandingMoment;
  };
  loop: {
    title: string;
    listLabel: string;
    aiDoes: string;
    peopleDo: string;
    steps: readonly LandingStep[];
    closing: string;
  };
  proof: {
    title: string;
    dryingTitle: string;
    dryingBody: (topShare: string) => string;
    year: string;
    lift: string;
    detectionWeeks: string;
    smallCount: string;
    photoTitle: string;
    photoSize: (n: string) => string;
    agentTitle: string;
    agentValue: (passed: string, cases: string) => string;
    agentSize: (cases: string) => string;
    shortTitle: string;
    reignition: (input: ReignitionLineInput) => string;
    morePrefix: string;
    moreLink: string;
    moreSuffix: string;
  };
  where: {
    title: string;
    places: readonly LandingPlace[];
    licence: string;
    screensTitle: string;
    entries: readonly LandingEntry[];
  };
  team: string;
};

const EN: LandingCopy = {
  toggleLabel: "Language of this page",
  title: "Bara finds drying peat and sends a person to check it before it burns.",
  audience:
    "For the people who keep peat wet: an ops desk, local volunteers, repair teams and the fire brigade.",
  tourNote: "The guided tour takes under 5 minutes and runs on the live system.",
  startTour: "Start the guided tour",
  resumeTour: (step, total) => `Resume at step ${step} of ${total}`,
  explore: "Explore freely",
  problem: {
    title: "Wet peat is safe. Dry peat is fuel.",
    points: [
      {
        title: "What peat is",
        body: "Soil made of plants that never rotted, because they stayed under water for thousands of years. Wet, it does not burn. Dry, it burns like charcoal.",
      },
      {
        title: "Canals drain it",
        body: "People dig canals for farms and plantations. The water in the peat around them drops, and the top of the peat dries out.",
      },
      {
        title: "Dams hold the water back",
        body: "Canal dams keep the peat wet. But dams break, leak, or the water flows around them, and nobody may notice.",
      },
    ],
    stakes:
      "A peat fire can look out on top and keep burning underground, then come back days later. The smoke crosses borders. Satellites already see the peat drying, but a map does not send anyone to the dam.",
    diagram: {
      works: "Dam works: water stays high, peat stays wet",
      broken: "Dam broken: water drains, top peat dries",
      canal: "canal",
      dam: "dam",
      wetPeat: "wet peat",
      dryPeat: "dry peat: fuel",
      waterLine: "water line",
      smoulder: "fire can smoulder here",
      radarNote: "Bara sees the drop in the water line as drying in radar data.",
    },
  },
  moments: {
    title: "Before the dry season, and after a fire looks out.",
    before: {
      when: "Before the dry season",
      signal: "Drying risk",
      action: "Dam check",
      body: "Every week Bara ranks all 3,769 one-kilometre peat squares in the Riau data by how fast they dry. Dams near the driest squares get checked first. Fixing a dam weeks before the smoke is cheap.",
    },
    after: {
      when: "After a fire looks out",
      signal: "Re-ignition risk",
      action: "Patrol re-check",
      body: "When a fire goes quiet, a model scores where the burned peat may come back. A patrol goes back to the 3 riskiest spots. Smoke in a photo, or no answer by the deadline, goes straight to the fire brigade.",
    },
  },
  loop: {
    title: "Five steps, from a satellite signal to a person with a task.",
    listLabel: "The five steps",
    aiDoes: "AI does",
    peopleDo: "People do",
    steps: [
      {
        title: "Find dry peat",
        ai: "Reads radar and rain for every square, every week. Gemini explains why a square ranks high, using only real numbers.",
        people: "The ops desk checks the reason before acting.",
      },
      {
        title: "Send a named person",
        ai: "Picks the nearest free person and writes the task in their language.",
        people: "The volunteer goes to the dam.",
      },
      {
        title: "Read the evidence",
        ai: "Gemini reads the photo, video or voice note into a verdict.",
        people:
          "The volunteer sends the evidence. Unsure or wrong-place evidence goes to a person for review.",
      },
      {
        title: "Repair, patrol again, or call the brigade",
        ai: "Rules send smoke to the brigade. A missed deadline goes to another person or to the brigade. The brigade gets a brief in Indonesian and English.",
        people: "Repair teams and the brigade do the field work.",
      },
      {
        title: "Show the public",
        ai: "Writes the public bulletin in Indonesian and English.",
        people: "Anyone can see the risk and the record, with no sign-in.",
      },
    ],
    closing: "AI never puts out a fire. It makes sure the right person knows, in time, with proof.",
  },
  proof: {
    title: "What we measured, and where it falls short.",
    dryingTitle: "The drying ranking finds later fires",
    dryingBody: (topShare) =>
      `How many times more fire detections fell in the top ${topShare} of squares in the 1 to 4 weeks after than chance would give. 1x is chance.`,
    year: "Year",
    lift: "Lift",
    detectionWeeks: "Detection-weeks (n)",
    smallCount: "A year with few fires rests on a small count.",
    photoTitle: "Dam state read right from photos",
    photoSize: (n) => `n = ${n} photos`,
    agentTitle: "Agent test cases passed",
    agentValue: (passed, cases) => `${passed} of ${cases}`,
    agentSize: (cases) =>
      `n = ${cases} cases. Each one checks the exact tools the agent calls, in the exact order.`,
    shortTitle: "Where it falls short",
    reignition: ({ modelAuc, baselineAuc, positives, events }) =>
      `The re-ignition model does not beat a simple rule yet. On the test fires it scored AUC ${modelAuc}; ranking by days of detection scored ${baselineAuc}. Only ${positives} of ${events} fires came back, so the gap is inside the noise. We show both.`,
    morePrefix: "Full numbers and method: ",
    moreLink: "How well it works",
    moreSuffix: ", at the bottom of the public page.",
  },
  where: {
    title: "Tested on data. Not yet in the field.",
    places: [
      {
        name: "Riau, Indonesia",
        body: "Mostly peat, with a long history of severe fires and many canals and dams. That makes it the hardest test case. We do not run a field programme there.",
      },
      { name: "Congo Cuvette", body: "Drying ranking and map only." },
      { name: "Any area you draw", body: "Up to 2,500 km², inside the Riau or Congo data." },
    ],
    licence:
      "Public data downloads are licensed CC BY-NC-SA 4.0, because the peat map they use is.",
    screensTitle: "Open a screen",
    entries: [
      {
        to: "/public",
        label: "Public view",
        note: "Risk map, response record and bulletin. No sign-in.",
      },
      {
        to: "/ops",
        label: "Ops desk (judge mode)",
        note: "Ranked areas, cases, live agent steps and the review queue.",
      },
      {
        to: "/area/new",
        label: "Draw an area",
        note: "Draw inside the Riau or Congo data and get its top 20 drying spots.",
      },
      { to: "/join", label: "Join as a volunteer", note: "Get tasks by message." },
    ],
  },
  team: "Bara is built by team Faber Fathers for Google Cloud AI Builder Cup 2026: Rizqy EP, Rama Dhaniansyah, Rafizhafran Halmi and Ramel Akil Pratama.",
};

const ID: LandingCopy = {
  toggleLabel: "Bahasa halaman ini",
  title:
    "Bara menemukan gambut yang mulai kering dan mengirim orang untuk mengeceknya sebelum terbakar.",
  audience:
    "Untuk orang-orang yang menjaga gambut tetap basah: petugas pemantau, relawan setempat, tim perbaikan sekat, dan regu pemadam.",
  tourNote:
    "Tur terpandu selesai dalam kurang dari 5 menit, langsung di sistem yang sedang berjalan. Tur ini berbahasa Inggris.",
  startTour: "Mulai tur terpandu",
  resumeTour: (step, total) => `Lanjutkan di langkah ${step} dari ${total}`,
  explore: "Jelajahi sendiri",
  problem: {
    title: "Gambut basah aman. Gambut kering jadi bahan bakar.",
    points: [
      {
        title: "Apa itu gambut",
        body: "Tanah dari sisa tumbuhan yang tidak membusuk karena terendam air selama ribuan tahun. Selama basah, gambut tidak terbakar. Begitu kering, ia terbakar seperti arang.",
      },
      {
        title: "Kanal mengeringkannya",
        body: "Orang menggali kanal untuk kebun dan perkebunan. Air di gambut sekitarnya turun, dan lapisan atasnya mengering.",
      },
      {
        title: "Sekat kanal menahan air",
        body: "Sekat kanal menahan air supaya gambut tetap basah. Tapi sekat bisa jebol, bocor, atau airnya lewat dari samping, dan bisa saja tidak ada yang tahu.",
      },
    ],
    stakes:
      "Api gambut bisa terlihat padam di permukaan tapi terus membara di bawah tanah, lalu muncul lagi beberapa hari kemudian. Asapnya sampai melintasi batas negara. Satelit sudah bisa melihat gambut mengering, tapi peta tidak mengirim siapa pun ke sekat.",
    diagram: {
      works: "Sekat utuh: air tetap tinggi, gambut tetap basah",
      broken: "Sekat jebol: air terkuras, gambut bagian atas mengering",
      canal: "kanal",
      dam: "sekat",
      wetPeat: "gambut basah",
      dryPeat: "gambut kering: bahan bakar",
      waterLine: "muka air",
      smoulder: "api bisa membara di sini",
      radarNote: "Bara melihat turunnya muka air ini sebagai tanda mengering di data radar.",
    },
  },
  moments: {
    title: "Sebelum kemarau, dan setelah api tampak padam.",
    before: {
      when: "Sebelum kemarau",
      signal: "Risiko kering",
      action: "Cek sekat",
      body: "Setiap minggu Bara mengurutkan 3.769 petak gambut seluas satu kilometer persegi di data Riau, dari yang paling cepat mengering. Sekat di dekat petak terkering dicek lebih dulu. Memperbaiki sekat berminggu-minggu sebelum ada asap jauh lebih murah.",
    },
    after: {
      when: "Setelah api tampak padam",
      signal: "Risiko menyala lagi",
      action: "Patroli ulang",
      body: "Saat api tampak padam, sebuah model menilai bagian bekas terbakar yang bisa menyala lagi. Patroli kembali ke 3 titik paling berisiko. Kalau foto menunjukkan asap, atau tidak ada jawaban sampai batas waktu, kasusnya langsung diteruskan ke regu pemadam.",
    },
  },
  loop: {
    title: "Lima langkah, dari sinyal satelit sampai ada orang yang memegang tugas.",
    listLabel: "Lima langkah",
    aiDoes: "Dikerjakan AI",
    peopleDo: "Dikerjakan manusia",
    steps: [
      {
        title: "Temukan gambut kering",
        ai: "Membaca data radar dan hujan untuk setiap petak, setiap minggu. Gemini menjelaskan kenapa sebuah petak berperingkat tinggi, hanya dengan angka yang benar-benar ada.",
        people: "Petugas pemantau memeriksa alasannya sebelum bertindak.",
      },
      {
        title: "Tunjuk satu orang",
        ai: "Memilih orang terdekat yang sedang luang dan menulis tugasnya dalam bahasa orang itu.",
        people: "Relawan berangkat ke sekat.",
      },
      {
        title: "Baca buktinya",
        ai: "Gemini membaca foto, video, atau pesan suara lalu menyimpulkan kondisinya.",
        people:
          "Relawan mengirim bukti. Bukti yang meragukan atau diambil di lokasi yang salah diperiksa oleh orang.",
      },
      {
        title: "Perbaiki, patroli lagi, atau panggil regu pemadam",
        ai: "Aturan meneruskan temuan asap ke regu pemadam. Tugas yang lewat batas waktu dialihkan ke orang lain atau ke regu pemadam. Regu pemadam menerima ringkasan dalam bahasa Indonesia dan Inggris.",
        people: "Tim perbaikan dan regu pemadam bekerja di lapangan.",
      },
      {
        title: "Tunjukkan ke publik",
        ai: "Menulis buletin publik dalam bahasa Indonesia dan Inggris.",
        people: "Siapa pun bisa melihat risikonya dan catatan penanganannya, tanpa masuk akun.",
      },
    ],
    closing:
      "AI tidak memadamkan api. AI memastikan orang yang tepat tahu, tepat waktu, dengan bukti.",
  },
  proof: {
    title: "Apa yang kami ukur, dan di mana masih kurang.",
    dryingTitle: "Peringkat kering menangkap kebakaran berikutnya",
    dryingBody: (topShare) =>
      `Berapa kali lebih banyak titik api yang jatuh di ${topShare} petak teratas dalam 1 sampai 4 minggu berikutnya, dibandingkan jika hanya kebetulan. 1x berarti sama dengan kebetulan.`,
    year: "Tahun",
    lift: "Kelipatan",
    detectionWeeks: "Deteksi-minggu (n)",
    smallCount: "Angka untuk tahun dengan sedikit kebakaran bertumpu pada jumlah yang kecil.",
    photoTitle: "Kondisi sekat terbaca benar dari foto",
    photoSize: (n) => `n = ${n} foto`,
    agentTitle: "Kasus uji agen yang lolos",
    agentValue: (passed, cases) => `${passed} dari ${cases}`,
    agentSize: (cases) =>
      `n = ${cases} kasus. Tiap kasus memeriksa alat yang dipanggil agen dan urutannya, harus persis.`,
    shortTitle: "Yang belum berhasil",
    reignition: ({ modelAuc, baselineAuc, positives, events }) =>
      `Model penyalaan ulang belum mengalahkan aturan sederhana. Pada data uji, AUC model ${modelAuc}; mengurutkan berdasarkan jumlah hari terdeteksi mendapat ${baselineAuc}. Hanya ${positives} dari ${events} kebakaran yang menyala lagi, jadi selisihnya masih bisa karena kebetulan. Kami menampilkan keduanya.`,
    morePrefix: "Angka lengkap dan metodenya: ",
    moreLink: "Seberapa baik hasilnya",
    moreSuffix: ", di bagian bawah halaman publik.",
  },
  where: {
    title: "Diuji dengan data. Belum di lapangan.",
    places: [
      {
        name: "Riau, Indonesia",
        body: "Sebagian besar gambut, dengan riwayat kebakaran parah yang panjang serta banyak kanal dan sekat. Karena itu Riau jadi kasus uji paling berat. Kami tidak menjalankan program lapangan di sana.",
      },
      { name: "Cuvette Kongo", body: "Hanya peringkat kering dan peta." },
      {
        name: "Area yang Anda gambar",
        body: "Hingga 2.500 km², di dalam cakupan data Riau atau Kongo.",
      },
    ],
    licence:
      "Data publik yang bisa diunduh berlisensi CC BY-NC-SA 4.0, mengikuti lisensi peta gambut yang dipakainya.",
    screensTitle: "Buka layar",
    entries: [
      {
        to: "/public",
        label: "Tampilan publik",
        note: "Peta risiko, catatan penanganan, dan buletin. Tanpa masuk akun.",
      },
      {
        to: "/ops",
        label: "Meja operasi (mode juri)",
        note: "Area berperingkat, kasus, langkah agen secara langsung, dan antrean tinjauan.",
      },
      {
        to: "/area/new",
        label: "Gambar area",
        note: "Gambar di dalam data Riau atau Kongo dan dapatkan 20 titik yang paling cepat mengering.",
      },
      { to: "/join", label: "Gabung sebagai relawan", note: "Dapatkan tugas lewat pesan." },
    ],
  },
  team: "Bara dibuat oleh tim Faber Fathers untuk Google Cloud AI Builder Cup 2026: Rizqy EP, Rama Dhaniansyah, Rafizhafran Halmi, dan Ramel Akil Pratama.",
};

const COPY: Record<CopyLanguage, LandingCopy> = { en: EN, id: ID };

export function landingCopy(language: CopyLanguage): LandingCopy {
  return COPY[language];
}
