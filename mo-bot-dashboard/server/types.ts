export interface User {
  id: number;
  fullName: string;
  role: string;
  roleName: string;
}

export interface BotEvent {
  id: string;
  timestamp: string; // ISO String
  timeFormatted: string; // e.g., "11:42"
  role: string;
  username: string;
  fullName: string;
  action: string;
  details: string;
  status: string;
}

export interface InventoryItem {
  name: string;
  category: string;
  quantity: number;
  unit: string;
  status: "Нормал" | "Кам қолди" | "Тугади";
  minThreshold: number;
}

export interface TransportOrder {
  id: string;
  driverName: string;
  vehicle: string;
  material: string;
  quantity: string;
  destination: string;
  status: string;
  progress: number;
  speed: number;
  gpsStatus: string;
}

export interface MechanicReport {
  id: string;
  vehicle: string;
  issue: string;
  status: string;
  assignedMechanic: string;
  fuelDistributed: number;
}

export interface AttendanceLog {
  id: string;
  employeeName: string;
  role: string;
  timestamp: string;
  timeFormatted: string;
  status: string;
  deviceId: string;
  deviceName: string;
}
