import { Router } from "express";
import * as XLSX from "xlsx";
import { 
  fetchBotEvents, 
  fetchInventory, 
  fetchTransportOrders, 
  fetchVehicles,
  fetchMechanicStatus,
  fetchUsers,
  pool 
} from "./db.js";
import { AttendanceLog, BotEvent } from "./types.js";

export const router = Router();

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
    const vehicles = await fetchVehicles();
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
      vehicles,
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

