import type { CaseStatus, CaseType, DamState, ExplanationEffect } from "../contracts";
import type { CopyLanguage } from "./language";

export type MapKeyScreen = "ops" | "public" | "area";

export type ScoreBands = readonly [string, string, string, string, string];

export type DetailCopy = {
  close: string;
  sections: { what: string; why: string; numbers: string };
  key: {
    title: string;
    explainToggle: string;
    explain: Record<MapKeyScreen, string>;
    cell: string;
    scaleLow: string;
    scaleHigh: string;
    dam: string;
    case: string;
    areaShape: string;
    areaCell: string;
    burnScar: string;
    reignition: string;
    peat: string;
    opacity: string;
    week: (week: string) => string;
    noLayers: string;
  };
  damStates: Record<DamState, string>;
  bands: ScoreBands;
  caseTypes: Record<CaseType, string>;
  caseWhat: Record<CaseType, string>;
  statuses: Record<CaseStatus, string>;
  facts: {
    score: string;
    rank: string;
    rankOf: (rank: number, total: number) => string;
    rankLine: (rank: string, total: string) => string;
    rankChange: string;
    radar: string;
    rain30: string;
    rainVsNormal: string;
    rainLess: (percent: string) => string;
    rainMore: (percent: string) => string;
    rainAboutNormal: string;
    canal: string;
    peatClass: string;
    trend: string;
    trendText: (first: string, last: string, weeks: number) => string;
    nearbyDams: string;
    pastFires: string;
    fireLine: (start: string, chance: string | null) => string;
    reignite: string;
    timeLeft: string;
    noOpenTask: string;
    evidence: string;
    lastState: string;
    lastChecked: string;
    neverChecked: string;
    repairDue: string;
    noRepairDue: string;
    areaSize: string;
    peatCells: string;
    notAvailable: string;
    groupWeather: string;
    groupLand: string;
  };
  meanings: {
    drier: string;
    wetter: string;
    noRadar: string;
    lessRain: string;
    moreRain: string;
    normalRain: string;
    up: (places: number) => string;
    down: (places: number) => string;
    same: string;
    isNew: string;
  };
  rankChangeShort: {
    up: (places: number) => string;
    down: (places: number) => string;
    same: string;
    isNew: string;
  };
  cell: {
    title: (id: string) => string;
    what: string;
    whyMissing: string;
    openCase: string;
    zoom: string;
    openCaseNote: string;
    send: {
      action: string;
      sending: string;
      sent: string;
      caseOpen: string;
      noFlow: string;
      failed: string;
    };
    how: { title: string; model: string; promptVersion: string };
    drivers: { label: string; effects: Record<ExplanationEffect, string> };
  };
  dam: {
    title: (id: string) => string;
    what: string;
    why: string;
    showArea: string;
    openCase: string;
    missing: string;
    checkedAt: (when: string) => string;
  };
  case: {
    title: (type: string, cellId: string) => string;
    example: string;
    whyMissing: string;
    assignedTo: (id: string) => string;
    showArea: string;
    timeline: string;
    evidenceTitle: string;
    agentRuns: string;
  };
  review: {
    title: (type: string, cellId: string) => string;
    chip: string;
    decision: string;
    keyLine: string;
    what: string;
    unsure: string;
    sure: string;
    confidence: string;
    noVerdict: string;
    openCase: string;
  };
  areaCell: {
    title: (id: string) => string;
    what: string;
    why: string;
    rankOfArea: (rank: number, total: number) => string;
    copy: string;
    copied: string;
    copyFailed: string;
  };
  publicDetail: {
    download: string;
  };
  ranked: {
    header: (week: string, ranked: string, total: string | null) => string;
    filterLabel: string;
    filters: { all: string; needsPerson: string; caseOpen: string };
    listLabel: (week: string) => string;
    empty: string;
    brokenDam: string;
    radar: (dB: string) => string;
    rain: (percent: string) => string;
    canal: (meters: string) => string;
  };
};

const EN_CELL = "a 1 km peat area";
const EN_DAM = "a canal dam";
const EN_AREA_CELL = "a ranked peat cell inside the area you drew";

const EN: DetailCopy = {
  close: "Close",
  sections: { what: "What it is", why: "Why it matters", numbers: "Numbers" },
  key: {
    title: "Map key",
    explainToggle: "What am I looking at?",
    explain: {
      ops: "Each square is a 1 km peat area. Bara ranks every square each week by how fast it dries, from satellite radar, rain and distance to a canal. Click a square or a dam to see the numbers and what to do next. The boxes above the map add more layers.",
      public:
        "Each square is a 1 km peat area. Bara ranks every square each week by how fast it dries, from satellite radar, rain and distance to a canal. Click a square or a dam for details. The boxes on the map add more layers.",
      area: "You drew an area. Bara found the peat cells inside it and ranked them the same way. Click a row or a circle to see one cell.",
    },
    cell: `Square = ${EN_CELL}. Colour = how fast it is drying, 0 (slow) to 100 (fast).`,
    scaleLow: "0 slow",
    scaleHigh: "100 fast",
    dam: `Circle = ${EN_DAM}. Colour = its state at the last check.`,
    case: "Dark outline = open case: someone is checking this area.",
    areaShape: "Brown outline = the area you drew.",
    areaCell: `Circle = ${EN_AREA_CELL}. Colour = drying score, same 0 to 100 scale.`,
    burnScar: "Dark brown = burned area seen from satellite.",
    reignition: "Re-ignition risk: chance a burned area catches fire again, 0 (low) to 1 (high).",
    peat: "Peat map: green shows peat soil, class 1 and class 2.",
    opacity: "Layer opacity",
    week: (week) => `Week ${week}.`,
    noLayers: "No map layers are on.",
  },
  damStates: {
    intact: "Intact",
    damaged: "Damaged",
    broken: "Broken",
    overtopped: "Water over the top",
    not_applicable: "Not checked",
    unknown: "Not checked",
  },
  bands: ["Slow drying", "Some drying", "Drying", "Fast drying", "Very fast drying"],
  caseTypes: { dam_risk: "Dam risk", reignition: "Re-ignition risk", hotspot: "Hotspot" },
  caseWhat: {
    dam_risk:
      "A canal dam sits in a peat area that is drying fast. Someone checks the dam before the peat dries out.",
    reignition:
      "A fire here went quiet, but burned peat can smoulder underground and catch fire again. Someone patrols the area.",
    hotspot: "Satellites saw heat here. Someone checks whether the peat is burning.",
  },
  statuses: {
    open: "Open",
    assigned: "Assigned",
    reviewing: "Reviewing",
    resolved_pending_human: "Resolved, needs a person",
    human_review: "Needs review",
    overdue: "Overdue",
    escalated: "Escalated",
    monitoring: "Monitoring",
    closed: "Closed",
  },
  facts: {
    score: "Drying score",
    rank: "Rank",
    rankOf: (rank, total) => `${rank} of ${total}`,
    rankLine: (rank, total) => `Rank ${rank} of ${total}`,
    rankChange: "Since last week",
    radar: "Radar change",
    rain30: "Rain, 30 days",
    rainVsNormal: "Rain vs normal",
    rainLess: (percent) => `${percent}% less`,
    rainMore: (percent) => `${percent}% more`,
    rainAboutNormal: "About normal",
    canal: "Canal distance",
    peatClass: "Peat class",
    trend: "Trend",
    trendText: (first, last, weeks) => `${first} to ${last} over ${weeks} weeks`,
    nearbyDams: "Nearby dams",
    pastFires: "Past fires",
    fireLine: (start, chance) =>
      chance === null ? `Fire from ${start}` : `Fire from ${start}, ${chance} chance to restart`,
    reignite: "Re-ignition chance",
    timeLeft: "Time left on the task",
    noOpenTask: "No open task",
    evidence: "Evidence",
    lastState: "Last state",
    lastChecked: "Last checked",
    neverChecked: "Never checked",
    repairDue: "Repair due",
    noRepairDue: "No repair due",
    areaSize: "Area size",
    peatCells: "Peat cells in the area",
    notAvailable: "n/a",
    groupWeather: "Weather and radar",
    groupLand: "Land and canal",
  },
  meanings: {
    drier: "The surface got drier",
    wetter: "The surface got wetter",
    noRadar: "No radar pass this week",
    lessRain: "Less rain than normal",
    moreRain: "More rain than normal",
    normalRain: "Normal rain",
    up: (places) => `Up ${places} places`,
    down: (places) => `Down ${places} places`,
    same: "Same place as last week",
    isNew: "New in the ranking this week",
  },
  rankChangeShort: {
    up: (places) => `↑${places}`,
    down: (places) => `↓${places}`,
    same: "same",
    isNew: "new",
  },
  cell: {
    title: (id) => `Area ${id}`,
    what: `This square is ${EN_CELL}. Bara ranks it each week by how fast it is drying.`,
    whyMissing:
      "Dry peat burns easily and is hard to put out. The numbers below show why it ranks here.",
    openCase: "Open its case",
    zoom: "Zoom to area",
    openCaseNote: "Open case: someone is checking this area.",
    send: {
      action: "Send someone",
      sending: "Sending…",
      sent: "Bara is picking the nearest free person. The case shows in Cases in about 30 seconds.",
      caseOpen: "This area already has an open case.",
      noFlow: "People are not set up in this region yet.",
      failed: "Could not send. Try again.",
    },
    how: { title: "How this was written", model: "Model", promptVersion: "Prompt version" },
    drivers: {
      label: "What drives the score",
      effects: {
        raises: "Pushes the score up",
        lowers: "Holds the score down",
        small: "Adds little",
      },
    },
  },
  dam: {
    title: (id) => `Canal dam ${id}`,
    what: `This circle is ${EN_DAM}. A canal dam holds water in the peat.`,
    why: "A broken or damaged dam drains the canal, so the peat around it dries faster.",
    showArea: "Show the area",
    openCase: "Open its case",
    missing: "This dam is not in this week's ranking.",
    checkedAt: (when) => `Last checked ${when}`,
  },
  case: {
    title: (type, cellId) => `${type} at ${cellId}`,
    example: "Example data",
    whyMissing: "The agent has not decided yet.",
    assignedTo: (id) => `Assigned to ${id}`,
    showArea: "Show the area",
    timeline: "Timeline",
    evidenceTitle: "Evidence",
    agentRuns: "Agent runs",
  },
  review: {
    title: (type, cellId) => `Review: ${type} at ${cellId}`,
    chip: "Needs review",
    decision: "Needs a decision",
    keyLine: "Gemini read the evidence. A person picks what happens next.",
    what: "A volunteer sent evidence for this case. Gemini read it, and a person must confirm what happens next.",
    unsure: "Gemini is unsure, so a person checks it",
    sure: "Gemini is sure, but the case still needs a person",
    confidence: "Gemini confidence",
    noVerdict: "No verdict yet.",
    openCase: "Open the full case",
  },
  areaCell: {
    title: (id) => `Cell ${id}`,
    what: `This circle is ${EN_AREA_CELL}.`,
    why: "Bara ranks these cells the same way as the weekly map. A higher score means the peat is drying faster.",
    rankOfArea: (rank, total) => `Rank ${rank} of ${total}`,
    copy: "Copy cell ID",
    copied: "Cell ID copied.",
    copyFailed: "Could not copy. Select the ID in the title.",
  },
  publicDetail: {
    download: "Download this week's data",
  },
  ranked: {
    header: (week, ranked, total) =>
      total === null
        ? `Week ${week} · ${ranked} ranked areas`
        : `Week ${week} · ${ranked} ranked of ${total} areas`,
    filterLabel: "Show",
    filters: { all: "All", needsPerson: "Needs a person", caseOpen: "Case open" },
    listLabel: (week) => `Ranked areas, ${week}`,
    empty: "No areas match this filter.",
    brokenDam: "Broken dam in this area",
    radar: (dB) => `Radar: drier surface (${dB} dB)`,
    rain: (percent) => `Rain ${percent}% below normal`,
    canal: (meters) => `Canal ${meters} m away`,
  },
};

const ID_CELL = "petak gambut 1 km";
const ID_DAM = "sekat kanal";
const ID_AREA_CELL = "petak gambut berperingkat di dalam area yang Anda gambar";

const ID: DetailCopy = {
  close: "Tutup",
  sections: { what: "Apa ini", why: "Kenapa penting", numbers: "Angka" },
  key: {
    title: "Keterangan peta",
    explainToggle: "Ini peta apa?",
    explain: {
      ops: "Tiap kotak adalah petak gambut 1 km. Tiap minggu Bara mengurutkan semua petak menurut kecepatan keringnya, dari radar satelit, curah hujan, dan jarak ke kanal. Klik kotak atau sekat untuk melihat angka dan langkah berikutnya. Kotak centang di atas peta menambah lapisan.",
      public:
        "Tiap kotak adalah petak gambut 1 km. Tiap minggu Bara mengurutkan semua petak menurut kecepatan keringnya, dari radar satelit, curah hujan, dan jarak ke kanal. Klik kotak atau sekat untuk melihat rinciannya. Kotak centang di peta menambah lapisan.",
      area: "Anda menggambar sebuah area. Bara mencari petak gambut di dalamnya dan mengurutkannya dengan cara yang sama. Klik baris atau lingkaran untuk melihat satu petak.",
    },
    cell: `Kotak = ${ID_CELL}. Warna = seberapa cepat gambutnya mengering, 0 (lambat) sampai 100 (cepat).`,
    scaleLow: "0 lambat",
    scaleHigh: "100 cepat",
    dam: `Lingkaran = ${ID_DAM}. Warna = kondisinya saat terakhir dicek.`,
    case: "Garis tepi gelap = kasus terbuka: ada orang yang sedang mengecek area ini.",
    areaShape: "Garis cokelat = area yang Anda gambar.",
    areaCell: `Lingkaran = ${ID_AREA_CELL}. Warna = skor pengeringan, skala 0 sampai 100 yang sama.`,
    burnScar: "Cokelat tua = bekas terbakar, terlihat dari satelit.",
    reignition:
      "Risiko menyala lagi: peluang bekas terbakar terbakar lagi, 0 (rendah) sampai 1 (tinggi).",
    peat: "Peta gambut: hijau menandai tanah gambut, kelas 1 dan kelas 2.",
    opacity: "Ketebalan lapisan",
    week: (week) => `Minggu ${week}.`,
    noLayers: "Tidak ada lapisan peta yang menyala.",
  },
  damStates: {
    intact: "Utuh",
    damaged: "Rusak",
    broken: "Jebol",
    overtopped: "Air melimpas",
    not_applicable: "Belum dicek",
    unknown: "Belum dicek",
  },
  bands: ["Kering lambat", "Agak kering", "Mengering", "Kering cepat", "Kering sangat cepat"],
  caseTypes: {
    dam_risk: "Risiko sekat",
    reignition: "Risiko menyala lagi",
    hotspot: "Titik panas",
  },
  caseWhat: {
    dam_risk:
      "Ada sekat kanal di petak gambut yang cepat mengering. Seseorang mengecek sekatnya sebelum gambutnya kering.",
    reignition:
      "Api di sini sudah padam, tapi gambut bekas terbakar bisa membara di bawah tanah lalu menyala lagi. Seseorang berpatroli di area ini.",
    hotspot: "Satelit menangkap panas di sini. Seseorang mengecek apakah gambutnya terbakar.",
  },
  statuses: {
    open: "Terbuka",
    assigned: "Ditugaskan",
    reviewing: "Diperiksa",
    resolved_pending_human: "Selesai, perlu dicek orang",
    human_review: "Perlu dicek",
    overdue: "Terlambat",
    escalated: "Diteruskan",
    monitoring: "Dipantau",
    closed: "Ditutup",
  },
  facts: {
    score: "Skor pengeringan",
    rank: "Peringkat",
    rankOf: (rank, total) => `${rank} dari ${total}`,
    rankLine: (rank, total) => `Peringkat ${rank} dari ${total}`,
    rankChange: "Sejak minggu lalu",
    radar: "Perubahan radar",
    rain30: "Hujan, 30 hari",
    rainVsNormal: "Hujan dibanding normal",
    rainLess: (percent) => `${percent}% lebih sedikit`,
    rainMore: (percent) => `${percent}% lebih banyak`,
    rainAboutNormal: "Mendekati normal",
    canal: "Jarak ke kanal",
    peatClass: "Kelas gambut",
    trend: "Tren",
    trendText: (first, last, weeks) => `${first} ke ${last} dalam ${weeks} minggu`,
    nearbyDams: "Sekat terdekat",
    pastFires: "Kebakaran sebelumnya",
    fireLine: (start, chance) =>
      chance === null
        ? `Kebakaran sejak ${start}`
        : `Kebakaran sejak ${start}, peluang menyala lagi ${chance}`,
    reignite: "Peluang menyala lagi",
    timeLeft: "Sisa waktu tugas",
    noOpenTask: "Tidak ada tugas terbuka",
    evidence: "Bukti",
    lastState: "Kondisi terakhir",
    lastChecked: "Terakhir dicek",
    neverChecked: "Belum pernah dicek",
    repairDue: "Tenggat perbaikan",
    noRepairDue: "Tidak ada tenggat perbaikan",
    areaSize: "Luas area",
    peatCells: "Petak gambut di area ini",
    notAvailable: "t/a",
    groupWeather: "Cuaca dan radar",
    groupLand: "Lahan dan kanal",
  },
  meanings: {
    drier: "Permukaannya makin kering",
    wetter: "Permukaannya makin basah",
    noRadar: "Tidak ada lintasan radar minggu ini",
    lessRain: "Hujan lebih sedikit dari biasanya",
    moreRain: "Hujan lebih banyak dari biasanya",
    normalRain: "Hujan seperti biasa",
    up: (places) => `Naik ${places} peringkat`,
    down: (places) => `Turun ${places} peringkat`,
    same: "Peringkatnya sama dengan minggu lalu",
    isNew: "Baru masuk peringkat minggu ini",
  },
  rankChangeShort: {
    up: (places) => `↑${places}`,
    down: (places) => `↓${places}`,
    same: "tetap",
    isNew: "baru",
  },
  cell: {
    title: (id) => `Petak ${id}`,
    what: `Kotak ini adalah ${ID_CELL}. Tiap minggu Bara mengurutkannya menurut kecepatan keringnya.`,
    whyMissing:
      "Gambut kering mudah terbakar dan sulit dipadamkan. Angka di bawah menunjukkan kenapa petak ini ada di peringkat ini.",
    openCase: "Buka kasusnya",
    zoom: "Perbesar ke petak",
    openCaseNote: "Kasus terbuka: ada orang yang sedang mengecek area ini.",
    send: {
      action: "Kirim orang",
      sending: "Mengirim…",
      sent: "Bara sedang memilih orang terdekat yang bisa. Kasus muncul di Kasus dalam sekitar 30 detik.",
      caseOpen: "Area ini sudah punya kasus terbuka.",
      noFlow: "Orang belum disiapkan di wilayah ini.",
      failed: "Tidak bisa mengirim. Coba lagi.",
    },
    how: { title: "Cara teks ini ditulis", model: "Model", promptVersion: "Versi prompt" },
    drivers: {
      label: "Yang menentukan skor",
      effects: { raises: "Menaikkan skor", lowers: "Menahan skor", small: "Pengaruh kecil" },
    },
  },
  dam: {
    title: (id) => `Sekat kanal ${id}`,
    what: `Lingkaran ini adalah ${ID_DAM}. Sekat kanal menahan air di dalam gambut.`,
    why: "Sekat yang jebol atau rusak membuat air kanal terbuang, jadi gambut di sekitarnya lebih cepat kering.",
    showArea: "Lihat petaknya",
    openCase: "Buka kasusnya",
    missing: "Sekat ini tidak ada di peringkat minggu ini.",
    checkedAt: (when) => `Terakhir dicek ${when}`,
  },
  case: {
    title: (type, cellId) => `${type} di ${cellId}`,
    example: "Data contoh",
    whyMissing: "Agen belum mengambil keputusan.",
    assignedTo: (id) => `Ditugaskan ke ${id}`,
    showArea: "Lihat petaknya",
    timeline: "Linimasa",
    evidenceTitle: "Bukti",
    agentRuns: "Jalannya agen",
  },
  review: {
    title: (type, cellId) => `Periksa: ${type} di ${cellId}`,
    chip: "Perlu dicek",
    decision: "Perlu keputusan",
    keyLine: "Gemini sudah membaca bukti. Seseorang memilih langkah berikutnya.",
    what: "Relawan mengirim bukti untuk kasus ini. Gemini sudah membacanya, dan seseorang harus memastikan langkah berikutnya.",
    unsure: "Gemini belum yakin, jadi orang yang mengecek",
    sure: "Gemini cukup yakin, tapi kasus ini tetap perlu dicek orang",
    confidence: "Keyakinan Gemini",
    noVerdict: "Belum ada penilaian.",
    openCase: "Buka kasus lengkap",
  },
  areaCell: {
    title: (id) => `Petak ${id}`,
    what: `Lingkaran ini adalah ${ID_AREA_CELL}.`,
    why: "Bara mengurutkan petak ini dengan cara yang sama seperti peta mingguan. Skor makin tinggi berarti gambutnya makin cepat kering.",
    rankOfArea: (rank, total) => `Peringkat ${rank} dari ${total}`,
    copy: "Salin ID petak",
    copied: "ID petak tersalin.",
    copyFailed: "Gagal menyalin. Pilih ID di judul.",
  },
  publicDetail: {
    download: "Unduh data minggu ini",
  },
  ranked: {
    header: (week, ranked, total) =>
      total === null
        ? `Minggu ${week} · ${ranked} petak diperingkat`
        : `Minggu ${week} · ${ranked} dari ${total} petak diperingkat`,
    filterLabel: "Tampilkan",
    filters: { all: "Semua", needsPerson: "Perlu orang", caseOpen: "Kasus terbuka" },
    listLabel: (week) => `Petak berperingkat, ${week}`,
    empty: "Tidak ada petak yang cocok dengan filter ini.",
    brokenDam: "Ada bendungan jebol di petak ini",
    radar: (dB) => `Radar: permukaan lebih kering (${dB} dB)`,
    rain: (percent) => `Hujan ${percent}% di bawah normal`,
    canal: (meters) => `Kanal berjarak ${meters} m`,
  },
};

export function detailCopy(language: CopyLanguage): DetailCopy {
  return language === "en" ? EN : ID;
}
