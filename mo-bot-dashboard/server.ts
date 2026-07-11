import express from "express";
import path from "path";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";
import * as XLSX from "xlsx";

dotenv.config();

// Initialize Express
const app = express();
const PORT = 3001;

app.use(express.json());

// Initialize Gemini SDK with telemetry header
const geminiApiKey = process.env.GEMINI_API_KEY;
let ai: GoogleGenAI | null = null;
if (geminiApiKey) {
  ai = new GoogleGenAI({
    apiKey: geminiApiKey,
    httpOptions: {
      headers: {
        "User-Agent": "aistudio-build",
      },
    },
  });
}

// Global In-Memory Database for the MO (Moddiy-Texnika Ta'minoti) Bot Simulation
interface BotEvent {
  id: string;
  timestamp: string; // ISO String
  timeFormatted: string; // e.g., "11:42"
  role: "boshqaruvchi" | "mexanik" | "brigadir" | "br" | "yetkazib_beruvchi" | "skladchik";
  username: string;
  fullName: string;
  action: string;
  details: string;
  status: "Тасдиқланди" | "Кутиляпти" | "Бажарилди" | "Йўлда" | "Тугатилди" | "Рад этилди" | "Етказилди" | "Юкланмоқда" | "Соз" | "Таъмирланмоқда";
}

interface InventoryItem {
  name: string;
  category: string;
  quantity: number;
  unit: string;
  status: "Нормал" | "Кам қолди" | "Тугади";
  minThreshold: number;
}

interface TransportOrder {
  id: string;
  driverName: string;
  vehicle: string;
  material: string;
  quantity: string;
  destination: string;
  status: "Кутиляпти" | "Юкланмоқда" | "Йўлда" | "Етказилди";
  progress: number;
  speed: number;
  gpsStatus: "Faol" | "Oflayn" | "Yuklanmoqda";
}

interface MechanicReport {
  id: string;
  vehicle: string;
  issue: string;
  status: "Соз" | "Таъмирланмоқда" | "Кутиш жараёнида";
  assignedMechanic: string;
  fuelDistributed: number; // in Liters
}

interface AttendanceLog {
  id: string;
  employeeName: string;
  role: string;
  timestamp: string;
  timeFormatted: string;
  status: "Kirish" | "Chiqish" | "Kechikdi";
  deviceId: string;
  deviceName: string;
}

// Setup initial simulated state
let botEvents: BotEvent[] = [
  {
    id: "evt_101",
    timestamp: new Date(Date.now() - 4 * 3600000).toISOString(),
    timeFormatted: "08:15",
    role: "boshqaruvchi",
    username: "@diyor_manager",
    fullName: "Диёр Шукуров",
    action: "Янги топшириқ бириктирди",
    details: "Сергели-5 объектида пойдевор қуйиш ишларини бошлаш бўйича бригадага кўрсатма берилди.",
    status: "Тасдиқланди"
  },
  {
    id: "evt_102",
    timestamp: new Date(Date.now() - 3.5 * 3600000).toISOString(),
    timeFormatted: "08:45",
    role: "brigadir",
    username: "@farhod_brigada",
    fullName: "Фарҳод Каримов",
    action: "Материал сўради",
    details: "Пойдевор қуйиш учун 12 тонна Цемент М500 ва 5 тонна Арматура (А500С) буюртма берди.",
    status: "Кутиляпти"
  },
  {
    id: "evt_103",
    timestamp: new Date(Date.now() - 3 * 3600000).toISOString(),
    timeFormatted: "09:10",
    role: "br",
    username: "@aziz_br_operator",
    fullName: "Азиз Мелиев",
    action: "Буюртма режалаштирди",
    details: "Фарҳод Каримовнинг материал сўровини тасдиқлаб, буюртмани Склад-1 омборига йўналтирди.",
    status: "Тасдиқланди"
  },
  {
    id: "evt_104",
    timestamp: new Date(Date.now() - 2.5 * 3600000).toISOString(),
    timeFormatted: "09:30",
    role: "skladchik",
    username: "@elena_sklad",
    fullName: "Елена Петрова",
    action: "Материал берди",
    details: "Фарҳод Каримовнинг сўровига асосан 12т цемент va 5т арматурани юк машинасига ортиш учун чиқарди.",
    status: "Бажарилди"
  },
  {
    id: "evt_105",
    timestamp: new Date(Date.now() - 2 * 3600000).toISOString(),
    timeFormatted: "10:00",
    role: "mexanik",
    username: "@sardor_mexanik",
    fullName: "Сардор Алиев",
    action: "Ёқилғи тарқатди",
    details: "Юк машинаси (MAN, давлат рақами 01 777 AAA) учун 250 литр дизель ёқилғиси берди ва тизимда тасдиқлади.",
    status: "Бажарилди"
  },
  {
    id: "evt_106",
    timestamp: new Date(Date.now() - 1.5 * 3600000).toISOString(),
    timeFormatted: "10:20",
    role: "yetkazib_beruvchi",
    username: "@kamron_driver",
    fullName: "Камрон Рустамов",
    action: "Юкни қабул қилди",
    details: "Склад-1 дан 12т цемент ва 5т арматурани қабул қилиб, Сергели-5 объекти томон йўлга chiqdи.",
    status: "Йўлда"
  },
  {
    id: "evt_107",
    timestamp: new Date(Date.now() - 0.5 * 3600000).toISOString(),
    timeFormatted: "11:15",
    role: "mexanik",
    username: "@sardor_mexanik",
    fullName: "Сардор Алиев",
    action: "Техник кўрик ҳисоботи",
    details: "КамАЗ (01 123 BBB) русумли юк машинасининг тормоз тизими носозлиги сабабли таъмирлашга киритилди.",
    status: "Кутиляпти"
  }
];

let inventory: InventoryItem[] = [
  { name: "Бетон блоки FBS", category: "Тайёр маҳсулот", quantity: 85, unit: "дона", status: "Нормал", minThreshold: 20 },
  { name: "Тротуар плиткаси", category: "Тайёр маҳсулот", quantity: 450, unit: "м²", status: "Нормал", minThreshold: 100 },
  { name: "Йўл бордюри", category: "Тайёр маҳсулот", quantity: 20, unit: "дона", status: "Кам қолди", minThreshold: 50 },
  { name: "Цемент М500", category: "Бутловчи маҳсулот", quantity: 185, unit: "тонна", status: "Нормал", minThreshold: 30 },
  { name: "Арматура А500С", category: "Бутловчи маҳсулот", quantity: 42, unit: "тонна", status: "Нормал", minThreshold: 15 },
  { name: "Ғишт (Пишган)", category: "Бутловчи маҳсулот", quantity: 65000, unit: "дона", status: "Нормал", minThreshold: 10000 },
  { name: "Шағал", category: "Бутловчи маҳсулот", quantity: 120, unit: "м³", status: "Нормал", minThreshold: 40 },
  { name: "Қум (Ювилган)", category: "Бутловчи маҳсулот", quantity: 8, unit: "м³", status: "Кам қолди", minThreshold: 25 },
  { name: "Дизель ёқилғиси", category: "Бутловчи маҳсулот", quantity: 1800, unit: "литр", status: "Нормал", minThreshold: 1000 },
  { name: "Шпатлевка", category: "Бутловчи маҳсулот", quantity: 0, unit: "қоп", status: "Тугади", minThreshold: 50 }
];

let transportOrders: TransportOrder[] = [
  {
    id: "TR-1024",
    driverName: "Камрон Рустамов",
    vehicle: "MAN (01 777 AAA)",
    material: "Цемент ва Арматура",
    quantity: "17 тонна",
    destination: "Tinchlik MFY Ob'ekti",
    status: "Йўлда",
    progress: 75,
    speed: 62,
    gpsStatus: "Faol"
  },
  {
    id: "TR-1025",
    driverName: "Достон Олимов",
    vehicle: "Howo (01 456 CCC)",
    material: "Шағал",
    quantity: "20 м³",
    destination: "Navro'z MFY Ob'ekti",
    status: "Юкланмоқда",
    progress: 15,
    speed: 0,
    gpsStatus: "Yuklanmoqda"
  },
  {
    id: "TR-1026",
    driverName: "Жасур Эргашев",
    vehicle: "Isuzu (01 987 DDD)",
    material: "Ғишт (15,000 дона)",
    quantity: "15,000 дона",
    destination: "Gulbahor Qo'rg'oni",
    status: "Кутиляпти",
    progress: 0,
    speed: 0,
    gpsStatus: "Faol"
  }
];

let mechanicStatus: MechanicReport[] = [
  { id: "VEH-101", vehicle: "MAN (01 777 AAA)", issue: "Йўқ (Сафар олди кўрикдан ўтди)", status: "Соз", assignedMechanic: "Сардор Алиев", fuelDistributed: 250 },
  { id: "VEH-102", vehicle: "Howo (01 456 CCC)", issue: "Гидравлика мойи алмаштирилди", status: "Соз", assignedMechanic: "Сардор Алиев", fuelDistributed: 180 },
  { id: "VEH-103", vehicle: "KamAZ (01 123 BBB)", issue: "Тормоз тизимидаги носозлик", status: "Таъмирланмоқда", assignedMechanic: "Сардор Алиев", fuelDistributed: 0 },
  { id: "VEH-104", vehicle: "Isuzu (01 987 DDD)", issue: "Мотор тақиллаши аниқланди", status: "Кутиш жараёнида", assignedMechanic: "Сардор Алиев", fuelDistributed: 80 }
];

let attendanceLogs: AttendanceLog[] = [
  {
    id: "ATT_101",
    employeeName: "Сардор Алиев",
    role: "mexanik",
    timestamp: new Date(Date.now() - 3.8 * 3600000).toISOString(),
    timeFormatted: "08:02",
    status: "Kirish",
    deviceId: "ZK-F22-01",
    deviceName: "ZKTeco F22 (Garaj)"
  },
  {
    id: "ATT_102",
    employeeName: "Диёр Шукуrov",
    role: "boshqaruvchi",
    timestamp: new Date(Date.now() - 3.7 * 3600000).toISOString(),
    timeFormatted: "08:05",
    status: "Kirish",
    deviceId: "ZK-F22-02",
    deviceName: "ZKTeco F22 (Ofis)"
  },
  {
    id: "ATT_103",
    employeeName: "Фарҳод Каримов",
    role: "brigadir",
    timestamp: new Date(Date.now() - 3.5 * 3600000).toISOString(),
    timeFormatted: "08:15",
    status: "Kirish",
    deviceId: "ZK-F22-03",
    deviceName: "ZKTeco F22 (Sklad)"
  },
  {
    id: "ATT_104",
    employeeName: "Елена Петрова",
    role: "skladchik",
    timestamp: new Date(Date.now() - 3.2 * 3600000).toISOString(),
    timeFormatted: "08:20",
    status: "Kirish",
    deviceId: "ZK-F22-03",
    deviceName: "ZKTeco F22 (Sklad)"
  }
];

// Active SSE client connections
let sseClients: any[] = [];

// Broadcast event helper
function broadcastEvent(event: BotEvent) {
  const payload = JSON.stringify(event);
  sseClients.forEach((client) => {
    client.res.write(`data: ${payload}\n\n`);
  });
}

// Simulation Engine: generates a random bot event
const firstNames = ["Фарҳод", "Сардор", "Елена", "Диёр", "Азиз", "Камрон", "Шавкат", "Бобур", "Зафар", "Жасур", "Музаффар", "Рустам"];
const lastNames = ["Каримов", "Алиев", "Петрова", "Шукуров", "Мелиев", "Рустамов", "Юсупов", "Раҳимов", "Турсунов", "Қодиров", "Умаров", "Содиқов"];

const eventTemplates: {
  role: "boshqaruvchi" | "mexanik" | "brigadir" | "br" | "yetkazib_beruvchi" | "skladchik";
  action: string;
  detailsGenerator: () => { text: string; updateState?: () => void };
  status: "Тасдиқланди" | "Кутиляпти" | "Бажарилди" | "Йўлда" | "Тугатилди" | "Рад этилди" | "Етказилди" | "Юкланмоқда" | "Соз" | "Таъмирланмоқда";
}[] = [
  {
    role: "brigadir",
    action: "Материал сўради",
    status: "Кутиляпти",
    detailsGenerator: () => {
      const items = ["Цемент М500", "Арматура А500С", "Ғишт (Пишган)", "Шағал", "Қум (Ювилган)"];
      const selected = items[Math.floor(Math.random() * items.length)];
      const val = selected.includes("Ғишт") ? "5000 дона" : (selected.includes("Қум") || selected.includes("Шағал") ? "15 м³" : "8 тонна");
      const subObj = ["Tinchlik MFY Ob'ekti", "Navro'z MFY Ob'ekti", "Gulbahor Qo'rg'oni", "Niyozbosh Ob'ekti", "Binokor MFY Ob'ekti", "Vokzal Ob'ekti"][Math.floor(Math.random() * 6)];
      return {
        text: `Объект: ${subObj} учун shoishilinch ${val} ${selected} so'rab buyurtma yaratdi.`
      };
    }
  },
  {
    role: "br",
    action: "Буюртма режалаштирди",
    status: "Тасдиқланди",
    detailsGenerator: () => {
      const driver = firstNames[Math.floor(Math.random() * firstNames.length)] + " " + lastNames[Math.floor(Math.random() * lastNames.length)];
      const loc = ["Tinchlik MFY", "Navro'z MFY", "Gulbahor", "Niyozbosh", "Binokor MFY", "Vokzal"][Math.floor(Math.random() * 6)];
      return {
        text: `Оператор ${driver}га янги транспорт маршрутини режалаштирdi. Манзил: ${loc} қурилиш участкаси.`,
        updateState: () => {
          const id = "TR-" + Math.floor(1000 + Math.random() * 9000);
          transportOrders.push({
            id,
            driverName: driver,
            vehicle: ["MAN (01 777 AAA)", "Howo (01 456 CCC)", "Isuzu (01 987 DDD)"][Math.floor(Math.random() * 3)],
            material: ["Цемент", "Ғишт", "Арматура", "Шағал"][Math.floor(Math.random() * 4)],
            quantity: Math.floor(5 + Math.random() * 15) + " бирлик",
            destination: loc + " Ob'ekti",
            status: "Юкланмоқда",
            progress: 10,
            speed: 0,
            gpsStatus: "Yuklanmoqda"
          });
        }
      };
    }
  },
  {
    role: "skladchik",
    action: "Юк келди",
    status: "Бажарилди",
    detailsGenerator: () => {
      const materials = ["Цемент М500", "Арматура А500С", "Ғишт (Пишган)", "Шағал", "Қум (Ювилган)", "Дизель ёқилғиси"];
      const mat = materials[Math.floor(Math.random() * materials.length)];
      const amount = mat.includes("Ғишт") ? 10000 : (mat.includes("ёқилғи") ? 500 : 15);
      return {
        text: `Ташқи етказиб берувчидан ${amount} ${inventory.find(i => i.name === mat)?.unit || ""} янги ${mat} қабул қилди ва захирага қўшди.`,
        updateState: () => {
          const item = inventory.find(i => i.name === mat);
          if (item) {
            item.quantity += amount;
            item.status = item.quantity > item.minThreshold ? "Нормал" : "Кам қолди";
          }
        }
      };
    }
  },
  {
    role: "skladchik",
    action: "Материал берди",
    status: "Бажарилди",
    detailsGenerator: () => {
      const items = ["Цемент М500", "Арматура А500С", "Ғишт (Пишган)", "Шағал", "Қум (Ювилган)"];
      const mat = items[Math.floor(Math.random() * items.length)];
      const amount = mat.includes("Ғишт") ? 2000 : 5;
      return {
        text: `Бригадир ҳисобига ${amount} ${inventory.find(i => i.name === mat)?.unit || ""} ${mat} омбордан чиқариб берди.`,
        updateState: () => {
          const item = inventory.find(i => i.name === mat);
          if (item) {
            item.quantity = Math.max(0, item.quantity - amount);
            item.status = item.quantity === 0 ? "Тугади" : (item.quantity <= item.minThreshold ? "Кам қолди" : "Нормал");
          }
        }
      };
    }
  },
  {
    role: "yetkazib_beruvchi",
    action: "Манзилга етиб борди",
    status: "Етказилди",
    detailsGenerator: () => {
      let text = "Етказиб берувчи юкни пойдевор қурилиш майдонига тўлиқ туширди.";
      const pendingIdx = transportOrders.findIndex(t => t.status === "Йўлда" || t.status === "Юкланмоқда");
      if (pendingIdx !== -1) {
        const order = transportOrders[pendingIdx];
        text = `Ҳайдовчи ${order.driverName} юкни (${order.material}, ${order.quantity}) ${order.destination} манзилига хавфсиз етказди.`;
        transportOrders[pendingIdx].status = "Етказилди";
        transportOrders[pendingIdx].progress = 100;
        transportOrders[pendingIdx].speed = 0;
        transportOrders[pendingIdx].gpsStatus = "Faol";
      }
      return { text };
    }
  },
  {
    role: "mexanik",
    action: "Ёқилғи тарқатди",
    status: "Бажарилди",
    detailsGenerator: () => {
      const amount = Math.floor(50 + Math.random() * 150);
      const vehicles = ["MAN (01 777 AAA)", "Howo (01 456 CCC)", "Isuzu (01 987 DDD)"];
      const chosenVeh = vehicles[Math.floor(Math.random() * vehicles.length)];
      return {
        text: `Техника ${chosenVeh} учун ${amount} литр дизель ёқилғиси қуйилди.`,
        updateState: () => {
          const fuel = inventory.find(i => i.name === "Дизель ёқилғиси");
          if (fuel) {
            fuel.quantity = Math.max(0, fuel.quantity - amount);
            fuel.status = fuel.quantity <= fuel.minThreshold ? "Кам қолди" : "Нормал";
          }
        }
      };
    }
  },
  {
    role: "mexanik",
    action: "Barmoq izi bosildi 👆",
    status: "Бажарилди",
    detailsGenerator: () => {
      const roles: ("boshqaruvchi" | "mexanik" | "brigadir" | "br" | "yetkazib_beruvchi" | "skladchik")[] = ["mexanik", "brigadir", "skladchik", "yetkazib_beruvchi", "boshqaruvchi"];
      const r = roles[Math.floor(Math.random() * roles.length)];
      const fName = firstNames[Math.floor(Math.random() * firstNames.length)];
      const lName = lastNames[Math.floor(Math.random() * lastNames.length)];
      const name = `${fName} ${lName}`;
      const statuses: ("Kirish" | "Chiqish" | "Kechikdi")[] = ["Kirish", "Kirish", "Kirish", "Chiqish"];
      const status = statuses[Math.floor(Math.random() * statuses.length)];
      const devices = [
        { id: "ZK-F22-01", name: "ZKTeco F22 (Garaj)" },
        { id: "ZK-F22-02", name: "ZKTeco F22 (Ofis)" },
        { id: "ZK-F22-03", name: "ZKTeco F22 (Sklad)" }
      ];
      const dev = devices[Math.floor(Math.random() * devices.length)];
      
      const updateState = () => {
        attendanceLogs.unshift({
          id: "ATT_" + Math.floor(100 + Math.random() * 900),
          employeeName: name,
          role: r,
          timestamp: new Date().toISOString(),
          timeFormatted: new Date().toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" }),
          status,
          deviceId: dev.id,
          deviceName: dev.name
        });
        if (attendanceLogs.length > 50) {
          attendanceLogs.pop();
        }
      };

      return {
        text: `Xodim ${name} (${r}) ${dev.name} qurilmasida barmoq izini bosdi. Holat: ${status}.`,
        updateState
      };
    }
  }
];

function triggerSimulationEvent() {
  const template = eventTemplates[Math.floor(Math.random() * eventTemplates.length)];
  const fName = firstNames[Math.floor(Math.random() * firstNames.length)];
  const lName = lastNames[Math.floor(Math.random() * lastNames.length)];
  const fullName = `${fName} ${lName}`;
  const username = `@${fName.toLowerCase()}_${lName.toLowerCase()}`;
  
  const generated = template.detailsGenerator();
  if (generated.updateState) {
    generated.updateState();
  }
  
  const now = new Date();
  const timeFormatted = now.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" });
  
  const newEvent: BotEvent = {
    id: "evt_" + Math.floor(100 + Math.random() * 900),
    timestamp: now.toISOString(),
    timeFormatted,
    role: template.role,
    username,
    fullName,
    action: template.action,
    details: generated.text,
    status: template.status
  };
  
  botEvents.unshift(newEvent);
  broadcastEvent(newEvent);
  return newEvent;
}

// Run simulation interval every 12 seconds
setInterval(() => {
  try {
    triggerSimulationEvent();
  } catch (err) {
    console.error("Simulation tick failed:", err);
  }
}, 12000);

// API Routes
app.get("/api/state", (req, res) => {
  const totalLogsCount = botEvents.length;
  const pendingOrdersCount = transportOrders.filter(t => t.status === "Йўлда" || t.status === "Юкланмоқда" || t.status === "Кутиляпти").length;
  const activeVehiclesCount = mechanicStatus.filter(m => m.status === "Соз").length;
  const criticalMaterialsCount = inventory.filter(i => i.quantity <= i.minThreshold).length;
  const activeEmployeesCount = new Set(
    attendanceLogs.filter(a => a.status === "Kirish").map(a => a.employeeName)
  ).size;

  res.json({
    logs: botEvents,
    inventory,
    transportOrders,
    mechanicStatus,
    attendanceLogs,
    stats: {
      totalLogsCount,
      pendingOrdersCount,
      activeVehiclesCount,
      criticalMaterialsCount,
      activeEmployeesCount
    }
  });
});

app.get("/api/events", (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders();

  const clientId = Date.now().toString();
  const newClient = {
    id: clientId,
    res
  };
  sseClients.push(newClient);

  req.on("close", () => {
    sseClients = sseClients.filter(c => c.id !== clientId);
  });
});

app.post("/api/trigger-simulation", (req, res) => {
  const event = triggerSimulationEvent();
  res.json({ success: true, event });
});

app.get("/api/download-report", (req, res) => {
  // Map botEvents to row array for xlsx export
  const rows = botEvents.map((e, index) => ({
    "T/r": index + 1,
    "ID": e.id,
    "Сана / Вақт": e.timeFormatted,
    "Роль / Lavozim": e.role,
    "Фойдаланувчи": e.username,
    "Ходим исми": e.fullName,
    "Амал / Harakat": e.action,
    "Батафсил": e.details,
    "Ҳолат / Status": e.status
  }));

  // Create worksheet
  const ws = XLSX.utils.json_to_sheet(rows);
  
  // Create workbook
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Бот фаолият журнали");

  // Adjust column widths
  ws["!cols"] = [
    { wch: 6 },   // T/r
    { wch: 12 },  // ID
    { wch: 14 },  // Sana / Vaqt
    { wch: 20 },  // Rol
    { wch: 20 },  // Foydalanuvchi
    { wch: 25 },  // Xodim ismi
    { wch: 25 },  // Amal
    { wch: 60 },  // Batafsil
    { wch: 15 }   // Holat
  ];

  // Write workbook to buffer
  const buffer = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });

  res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
  res.setHeader("Content-Disposition", `attachment; filename="MO_Kunlik_Hisobot_${new Date().toISOString().slice(0,10)}.xlsx"`);
  res.send(buffer);
});

// Gemini AI Auditor in Uzbek Language
app.post("/api/gemini/analyze", async (req, res) => {
  if (!ai) {
    return res.status(500).json({
      error: "Gemini API kaliti topilmadi. Iltimos, Secrets paneli orqali GEMINI_API_KEY kalitini kiriting.",
    });
  }

  try {
    const formattedLogs = botEvents.slice(0, 30).map(e => 
      `[${e.timeFormatted}] ${e.fullName} (${e.role}): ${e.action} -> ${e.details} [Status: ${e.status}]`
    ).join("\n");

    const formattedInventory = inventory.map(i => 
      `- ${i.name}: ${i.quantity} ${i.unit} (Status: ${i.status}, Limit: ${i.minThreshold})`
    ).join("\n");

    const formattedTransport = transportOrders.map(t => 
      `- ${t.id} (${t.driverName}): ${t.material} ketmoqda ${t.destination}ga. Status: ${t.status} (${t.progress}%)`
    ).join("\n");

    const formattedMechanic = mechanicStatus.map(m => 
      `- ${m.vehicle}: Nosozlik -> ${m.issue}, Status -> ${m.status}, Yoqilg'i -> ${m.fuelDistributed} L`
    ).join("\n");

    const prompt = `Siz "MO" (Moddiy-Texnika Ta'minoti) tizimining intellektual tahlilchisi va auditorisiz.
Quyida bugungi Telegram bot faolligi, ombordagi zaxiralar, transport va texnik holatlar jurnali berilgan.

Ushbu ma'lumotlarni o'rganib chiqib, Super Admin uchun o'ta professional, lo'nda va chiroyli tahliliy hisobot tayyorlang. Hisobot to'liq O'zbek tilida bo'lishi shart!

MA'LUMOTLAR JURNALI:
---
[TELEGRAM BOT LOGLARI]
${formattedLogs}

[OMBOR ZAXIRALARI]
${formattedInventory}

[YUK YETKAZIB BERISH ORDERS]
${formattedTransport}

[TEXNIKA VA MEXANIKA HOLATI]
${formattedMechanic}
---

TAYYORLANADIGAN HISOBOT TUZILISHI:
1. 📈 Kunlik faollikning umumiy tahlili (qisqa xulosa, bot orqali qancha ish rejalashtirildi).
2. ⚠️ Diqqat talab qiluvchi muammolar yoki xavflar (zaxirasi kam qolgan materiallar, buzilgan yuk mashinalari, kechikayotgan haydovchilar).
3. 👤 Rollar bo'yicha baholash (Boshqaruvchi, Mexanik, Brigadir, BR, Yetkazib beruvchi, Skladchik nimalar qildi, kim eng faol).
4. 💡 Tizim samaradorligini oshirish bo'yicha 3 ta amaliy tavsiya (masalan, yoqilg'i sarfi, logistika marshrutlari yoki zaxiralarni to'ldirish bo'yicha).

Iltimos, hisobotni juda o'qishga oson, chiroyli Markdown formatida va foydali ma'lumotlar bilan boyitilgan tarzda qaytaring. Keraksiz texnik so'zlarni kamaytirib, aniq biznes qiymatga e'tibor qarating.`;

    const response = await ai.models.generateContent({
      model: "gemini-3.5-flash",
      contents: prompt,
    });

    res.json({
      success: true,
      analysis: response.text,
    });
  } catch (error: any) {
    console.error("Gemini analysis failed:", error);
    res.status(500).json({
      error: "Sun'iy intellekt tahlilini yuklashda xatolik yuz berdi: " + error.message,
    });
  }
});

// Background tick to simulate vehicle progress and speed
setInterval(() => {
  transportOrders = transportOrders.map((order) => {
    if (order.status === "Йўлда") {
      const newProgress = Math.min(100, order.progress + Math.floor(Math.random() * 5) + 2);
      const isArrived = newProgress >= 100;
      return {
        ...order,
        progress: newProgress,
        status: isArrived ? "Етказилди" : "Йўлда",
        speed: isArrived ? 0 : Math.floor(50 + Math.random() * 20),
        gpsStatus: isArrived ? "Faol" : "Faol"
      };
    } else if (order.status === "Юкланмоқда") {
      const newProgress = Math.min(100, order.progress + Math.floor(Math.random() * 8) + 4);
      const isLoaded = newProgress >= 100;
      return {
        ...order,
        progress: isLoaded ? 0 : newProgress,
        status: isLoaded ? "Йўлда" : "Юкланмоқда",
        speed: 0,
        gpsStatus: "Yuklanmoqda"
      };
    } else if (order.status === "Кутиляпти") {
      if (Math.random() > 0.7) {
        return {
          ...order,
          status: "Юкланмоқда",
          progress: 5,
          speed: 0,
          gpsStatus: "Yuklanmoqda"
        };
      }
    }
    return order;
  });
}, 4000);

// Vite Dev Server / Production Static Serving
async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`MO Bot Dashboard server is running on http://localhost:${PORT}`);
  });
}

startServer();
