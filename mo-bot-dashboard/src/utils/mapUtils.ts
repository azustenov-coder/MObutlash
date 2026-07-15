export const yangiyolPoints: Record<string, { x: number; y: number; label: string }> = {
  sklad: { x: 300, y: 170, label: "Омбор (1-омбор)" },
  tinchlik: { x: 180, y: 290, label: "Tinchlik MFY" },
  navruz: { x: 80, y: 210, label: "Navro'z MFY" },
  gulbahor: { x: 480, y: 60, label: "Gulbahor Qo'rg'oni" },
  niyozbosh: { x: 200, y: 90, label: "Niyozbosh" },
  binokor: { x: 280, y: 40, label: "Binokor MFY" },
  vokzal: { x: 350, y: 130, label: "Yangiyo'l Vokzal" }
};

export const toshkentPoints: Record<string, { x: number; y: number; label: string }> = {
  sklad: { x: 300, y: 170, label: "Омбор (1-омбор)" },
  sergeli: { x: 180, y: 290, label: "Sergeli-5" },
  chilonzor: { x: 80, y: 210, label: "Chilonzor 9" },
  yunusobod: { x: 480, y: 60, label: "Yunusobod 12" },
  olmazor: { x: 200, y: 90, label: "Olmazor Res." },
  qoraqamish: { x: 280, y: 40, label: "Qoraqamish-3" },
  city: { x: 350, y: 130, label: "Tashkent City" }
};

export const getDestKey = (dest: string) => {
  const d = dest.toLowerCase();
  // Yangiyol keys
  if (d.includes("tinchlik")) return "tinchlik";
  if (d.includes("navr") || d.includes("навр")) return "navruz";
  if (d.includes("gulbahor") || d.includes("гулбаҳор")) return "gulbahor";
  if (d.includes("niyozbosh") || d.includes("ниёзбош")) return "niyozbosh";
  if (d.includes("binokor") || d.includes("бинокор")) return "binokor";
  if (d.includes("vokzal") || d.includes("вокзал")) return "vokzal";
  // Tashkent keys
  if (d.includes("sergeli") || d.includes("сергели")) return "sergeli";
  if (d.includes("chilonzor") || d.includes("чилонзор")) return "chilonzor";
  if (d.includes("yunusobod") || d.includes("юнусобод")) return "yunusobod";
  if (d.includes("olmazor") || d.includes("олмазор")) return "olmazor";
  if (d.includes("qoraqamish") || d.includes("қорақамиш")) return "qoraqamish";
  if (d.includes("city") || d.includes("сити")) return "city";
  return null;
};
