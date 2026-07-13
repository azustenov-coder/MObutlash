import { Router } from "express";
import { GoogleGenAI } from "@google/genai";
import * as XLSX from "xlsx";
import { 
  fetchBotEvents, 
  fetchInventory, 
  fetchTransportOrders, 
  fetchMechanicStatus,
  fetchUsers,
  pool 
} from "./db.js";
import { AttendanceLog, BotEvent } from "./types.js";

export const router = Router();

// Initialize Gemini SDK
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

// Active SSE client connections
let sseClients: any[] = [];
let lastEventId: string | null = null;

export function broadcastEvent(event: BotEvent) {
  const payload = JSON.stringify(event);
  sseClients.forEach((client) => {
    client.res.write(`data: ${payload}\n\n`);
  });
}

// Polling interval
setInterval(async () => {
  if (!pool) return;
  try {
    const logs = await fetchBotEvents();
    if (logs.length > 0) {
      const currentLatestId = logs[0].id;
      if (lastEventId === null) {
        lastEventId = currentLatestId;
      } else if (currentLatestId !== lastEventId) {
        broadcastEvent(logs[0]);
        lastEventId = currentLatestId;
      }
    }
  } catch (err) {
    console.error("Error polling db:", err);
  }
}, 5000);

router.get("/state", async (req, res) => {
  try {
    const botEvents = await fetchBotEvents();
    const inventory = await fetchInventory();
    const transportOrders = await fetchTransportOrders();
    const mechanicStatus = await fetchMechanicStatus();
    const users = await fetchUsers();
    const attendanceLogs: AttendanceLog[] = [];

    const totalLogsCount = botEvents.length;
    const pendingOrdersCount = transportOrders.filter(t => t.status === "Йўлда" || t.status === "Юкланмоқда" || t.status === "Кутиляпти").length;
    const activeVehiclesCount = mechanicStatus.filter(m => m.status === "Соз").length;
    const criticalMaterialsCount = inventory.filter(i => i.quantity <= i.minThreshold).length;
    const activeEmployeesCount = users.length;

    res.json({
      logs: botEvents,
      inventory,
      transportOrders,
      mechanicStatus,
      users,
      attendanceLogs,
      stats: {
        totalLogsCount,
        pendingOrdersCount,
        activeVehiclesCount,
        criticalMaterialsCount,
        activeEmployeesCount
      }
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

router.get("/events", (req, res) => {
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

router.post("/trigger-simulation", (req, res) => {
  res.json({ success: false, message: "Simulation disabled in real integration" });
});

router.get("/download-report", async (req, res) => {
  try {
    const botEvents = await fetchBotEvents();
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

    const ws = XLSX.utils.json_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Бот фаолият журнали");

    ws["!cols"] = [
      { wch: 6 },   { wch: 12 },  { wch: 14 },  { wch: 20 },
      { wch: 20 },  { wch: 25 },  { wch: 25 },  { wch: 60 },
      { wch: 15 }
    ];

    const buffer = XLSX.write(wb, { type: "buffer", bookType: "xlsx" });

    res.setHeader("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
    res.setHeader("Content-Disposition", `attachment; filename="MO_Kunlik_Hisobot_${new Date().toISOString().slice(0,10)}.xlsx"`);
    res.send(buffer);
  } catch (err: any) {
    res.status(500).send("Error generating report: " + err.message);
  }
});

router.post("/gemini/analyze", async (req, res) => {
  if (!ai) {
    return res.status(500).json({
      error: "Gemini API kaliti topilmadi.",
    });
  }

  try {
    const botEvents = await fetchBotEvents();
    const inventory = await fetchInventory();
    const transportOrders = await fetchTransportOrders();
    const mechanicStatus = await fetchMechanicStatus();

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
3. 👤 Rollar bo'yicha baholash.
4. 💡 Tizim samaradorligini oshirish bo'yicha 3 ta amaliy tavsiya.

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
    res.status(500).json({ error: "Xatolik: " + error.message });
  }
});
