import dotenv from 'dotenv';
import path from 'path';

// Load .env from the dashboard root directory
dotenv.config({ path: path.join(process.cwd(), '.env') });

import pkg from 'pg';
const { Pool } = pkg;
import { BotEvent, InventoryItem, TransportOrder, MechanicReport, User, Vehicle } from "./types.js";

export const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

export async function setupDatabase() {
  // Keeping this for backwards compatibility with server.ts
  console.log("Connected to Neon Postgres database");
}

function mapStatus(status: string): string {
  const map: Record<string, string> = {
    pending_approval: "Тасдиқлаш кутилмоқда",
    pending_admin_approval: "Админ кутилмоқда",
    approved: "Тасдиқланган",
    delivering: "Йўлда",
    searching: "Қидирилмоқда",
    purchased: "Сотиб олинди",
    waiting_receipt: "Қабул кутилмоқда",
    completed: "Якунланди",
    rejected: "Рад этилди",
    ready_for_installation: "Ўрнатишга тайёр"
  };
  return map[status] || status;
}

function getRoleName(role: string): string {
  const map: Record<string, string> = {
    'super_admin': 'Super Admin',
    'manager': 'Boshqaruvchi',
    'observer': 'Boshqaruvchi 2',
    'mechanic': 'Mexanik',
    'brigadir': 'Brigadir',
    'brigadier': 'Brigadir',
    'courier': "Ta'minotchi",
    'warehouseman': 'Skladchik'
  };
  return map[role] || role;
}

export async function fetchUsers(): Promise<User[]> {
  if (!pool) return [];
  const res = await pool.query(`SELECT telegram_id, full_name, role FROM users WHERE is_approved = 1 ORDER BY created_at ASC`);
  return res.rows.map((r: any) => ({
    id: r.telegram_id,
    fullName: r.full_name,
    role: r.role,
    roleName: getRoleName(r.role)
  }));
}

export async function fetchBotEvents(): Promise<BotEvent[]> {
  if (!pool) return [];
  const res = await pool.query(`
    SELECT r.id, r.created_at, u.role, u.full_name, u.phone as username, 
           r.request_type as action, r.description as details, r.status
    FROM requests r
    JOIN users u ON r.created_by = u.telegram_id
    ORDER BY r.created_at DESC
    LIMIT 50
  `);
  
  return res.rows.map(r => {
    const d = new Date(r.created_at);
    return {
      id: "REQ-" + r.id,
      timestamp: r.created_at.toISOString(),
      timeFormatted: d.toLocaleTimeString("uz-UZ", { timeZone: "Asia/Tashkent", hour: "2-digit", minute: "2-digit", hour12: false }),
      role: getRoleName(r.role),
      username: r.username,
      fullName: r.full_name,
      action: r.action === "purchase" ? "Сотиб олинган" : 
              r.action === "repair" ? "Таъмирланган" : 
              r.action === "both" ? "Таъмирланган ва Сотиб олинган" : 
              r.action,
      details: r.details,
      status: mapStatus(r.status),
      _lastId: "REQ-" + r.id
    };
  });
}

export async function fetchInventory(): Promise<InventoryItem[]> {
  if (!pool) return [];
  const res = await pool.query(`SELECT id, name, category, quantity FROM inventory`);
  return res.rows.map(r => ({
    name: r.name,
    category: r.category,
    quantity: r.quantity,
    unit: "дона",
    status: r.quantity === 0 ? "Тугади" : (r.quantity < 20 ? "Кам қолди" : "Нормал"),
    minThreshold: 20
  }));
}

export async function fetchTransportOrders(): Promise<TransportOrder[]> {
  if (!pool) return [];
  const res = await pool.query(`
    SELECT r.id, r.status, u.full_name as driver_name, r.vehicle_name
    FROM requests r
    LEFT JOIN users u ON r.courier_id = u.telegram_id
    WHERE r.status IN ('in_transit', 'delivered', 'warehouse_released')
    ORDER BY r.updated_at DESC
    LIMIT 20
  `);
  
  return res.rows.map(r => {
    let progress = 10;
    let speed = 0;
    if (r.status === 'in_transit') { progress = 50; speed = 60; }
    else if (r.status === 'delivered') { progress = 100; speed = 0; }
    
    return {
      id: "TR-" + r.id,
      driverName: r.driver_name || "Noma'lum",
      vehicle: r.vehicle_name || "Noma'lum",
      material: "Bir nechta mahsulotlar",
      quantity: "-",
      destination: "Obyekt",
      status: mapStatus(r.status),
      progress,
      speed,
      gpsStatus: "Faol"
    };
  });
}

export async function fetchVehicles(): Promise<Vehicle[]> {
  if (!pool) return [];
  const res = await pool.query(`
    SELECT name, driver_name, driver_phone, vehicle_model, status
    FROM vehicles
    ORDER BY CASE WHEN name ~ '^[0-9]+$' THEN name::integer ELSE 999999 END, name
  `);
  return res.rows.map((r: any) => ({
    name: r.name,
    driverName: r.driver_name || "Киритилмаган",
    driverPhone: r.driver_phone || "Киритилмаган",
    model: r.vehicle_model || "Киритилмаган",
    status: r.status === "soz" ? "Соз" : r.status === "nosoz" ? "Носоз" : (r.status || "Номаълум")
  }));
}

export async function fetchMechanicStatus(): Promise<MechanicReport[]> {
  if (!pool) return [];
  const res = await pool.query(`SELECT name, status, reason FROM vehicles`);
  return res.rows.map((r, i) => ({
    id: "VEH-" + (i+1),
    vehicle: r.name,
    issue: r.reason || "Йўқ",
    status: r.status === 'soz' ? 'Соз' : 'Таъмирланмоқда',
    assignedMechanic: "Mexanik",
    fuelDistributed: 0
  }));
}
