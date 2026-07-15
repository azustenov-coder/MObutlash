export interface User {
  id: number;
  fullName: string;
  role: string;
  roleName: string;
}

export interface BotEvent {
  id: string;
  timestamp: string;
  timeFormatted: string;
  role: "Super Admin" | "Boshqaruvchi" | "Mexanik" | "Brigadir" | "Ta'minotchi" | "Skladchik";
  username: string;
  fullName: string;
  action: string;
  details: string;
  status: "Тасдиқланди" | "Кутиляпти" | "Бажарилди" | "Йўлда" | "Етказилди" | "Рад этилди" | "Тугатилди" | "Соз" | "Таъмирланмоқда" | "Юкланмоқда";
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
  status: "Кутиляпти" | "Юкланмоqda" | "Йўлда" | "Етказилди" | "Юкланмоқда";
  progress: number;
  speed: number;
  gpsStatus: "Faol" | "Oflayn" | "Yuklanmoqda";
}

export interface Vehicle {
  name: string;
  driverName: string;
  driverPhone: string;
  model: string;
  status: string;
}

export interface MechanicReport {
  id: string;
  vehicle: string;
  issue: string;
  status: "Соз" | "Таъмирланмоқда" | "Кутиш жараёнида";
  assignedMechanic: string;
  fuelDistributed: number;
}

export interface AttendanceLog {
  id: string;
  employeeName: string;
  role: string;
  timestamp: string;
  timeFormatted: string;
  status: "Kirish" | "Chiqish" | "Kechikdi";
  deviceId: string;
  deviceName: string;
}

export interface DashboardStats {
  totalLogsCount: number;
  pendingOrdersCount: number;
  activeVehiclesCount: number;
  criticalMaterialsCount: number;
  activeEmployeesCount: number;
}

export interface DashboardState {
  logs: BotEvent[];
  inventory: InventoryItem[];
  transportOrders: TransportOrder[];
  vehicles: Vehicle[];
  mechanicStatus: MechanicReport[];
  users: User[];
  attendanceLogs: AttendanceLog[];
  stats: DashboardStats;
}
