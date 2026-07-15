import { TransportOrder } from "../../types";
import { getDestKey } from "../../utils/mapUtils";

interface MapWidgetProps {
  transportOrders: TransportOrder[];
  selectedMap: "yangiyol" | "toshkent";
  setSelectedMap: (val: "yangiyol" | "toshkent") => void;
  mapPoints: Record<string, { x: number; y: number; label: string }>;
}

export function MapWidget({ transportOrders, selectedMap, setSelectedMap, mapPoints }: MapWidgetProps) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
          </span>
          <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
            GPS Жонли кузатув харитаси
          </h3>
        </div>
        <select
          value={selectedMap}
          onChange={(e) => setSelectedMap(e.target.value as "yangiyol" | "toshkent")}
          className="bg-slate-950 text-xs font-mono font-bold text-slate-300 px-3 py-1.5 rounded-md border border-slate-800 focus:outline-none focus:border-indigo-500 cursor-pointer"
        >
          <option value="yangiyol">Янгийўл шаҳри харитаси</option>
          <option value="toshkent">Тошкент шаҳри харитаси</option>
        </select>
      </div>

      <div className="relative w-full overflow-hidden rounded-xl border border-slate-800 bg-[#060814] h-80">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(99,102,241,0.03)_0%,transparent_70%)] pointer-events-none" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#0b0f19_1px,transparent_1px),linear-gradient(to_bottom,#0b0f19_1px,transparent_1px)] bg-[size:2rem_2rem] opacity-30 pointer-events-none" />

        <svg className="w-full h-full" viewBox="0 0 600 350">
          <circle cx="300" cy="170" r="100" fill="none" stroke="#1e1b4b" strokeWidth="1" strokeDasharray="3 6" />
          <circle cx="300" cy="170" r="200" fill="none" stroke="#1e1b4b" strokeWidth="1" strokeDasharray="4 8" />

          {/* Draw Routes */}
          {Object.keys(mapPoints).map((key) => {
            if (key === "sklad") return null;
            const pt = mapPoints[key];
            const isRouteActive = transportOrders.some(
              (o) => o.status === "Йўлда" && getDestKey(o.destination) === key
            );

            return (
              <g key={key}>
                <line
                  x1={mapPoints.sklad.x}
                  y1={mapPoints.sklad.y}
                  x2={pt.x}
                  y2={pt.y}
                  stroke={isRouteActive ? "#4338ca" : "#1e293b"}
                  strokeWidth={isRouteActive ? "2.5" : "1.5"}
                  strokeDasharray={isRouteActive ? "none" : "5 5"}
                />
                {isRouteActive && (
                  <line
                    x1={mapPoints.sklad.x}
                    y1={mapPoints.sklad.y}
                    x2={pt.x}
                    y2={pt.y}
                    stroke="#6366f1"
                    strokeWidth="4"
                    className="opacity-20 animate-pulse"
                  />
                )}
              </g>
            );
          })}

          {/* Draw Destination Nodes */}
          {Object.keys(mapPoints).map((key) => {
            const pt = mapPoints[key];
            const isSklad = key === "sklad";
            const hasActiveVehicle = transportOrders.some(
              (o) => getDestKey(o.destination) === key && (o.status === "Йўлда" || o.status === "Етказилди")
            );

            return (
              <g key={key} className="select-none">
                {(isSklad || hasActiveVehicle) && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r={isSklad ? "14" : "10"}
                    className={`${isSklad ? "fill-red-500/10 stroke-red-500/30" : "fill-emerald-500/10 stroke-emerald-500/30"} stroke-2 animate-ping`}
                  />
                )}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isSklad ? "7" : "5"}
                  className={`${
                    isSklad ? "fill-red-500 stroke-red-400" :
                    hasActiveVehicle ? "fill-emerald-500 stroke-emerald-400" : "fill-slate-700 stroke-slate-600"
                  } stroke-2`}
                />
                <text
                  x={pt.x}
                  y={pt.y - (isSklad ? 12 : 9)}
                  textAnchor="middle"
                  fill="#94a3b8"
                  className="text-[9px] font-mono font-black tracking-tight"
                >
                  {pt.label}
                </text>
              </g>
            );
          })}

          {/* Draw Live Vehicles moving on Paths */}
          {transportOrders.map((order) => {
            const destKey = getDestKey(order.destination);
            if (!destKey || !mapPoints[destKey]) return null;

            const start = mapPoints.sklad;
            const end = mapPoints[destKey];
            const progress = order.progress / 100;

            const x = start.x + (end.x - start.x) * progress;
            const y = start.y + (end.y - start.y) * progress;

            if (order.status === "Кутиляпти") return null;

            const isArrived = order.status === "Етказилди";
            const isLoading = order.status === "Юкланмоқда";

            return (
              <g key={order.id} className="cursor-pointer group">
                <circle
                  cx={x}
                  cy={y}
                  r="12"
                  className={`${
                    isArrived ? "fill-emerald-500/10 stroke-emerald-500/40" :
                    isLoading ? "fill-amber-500/10 stroke-amber-500/40" : "fill-indigo-500/20 stroke-indigo-400/60"
                  } stroke-2 animate-pulse`}
                />
                <circle
                  cx={x}
                  cy={y}
                  r="5.5"
                  className={`${
                    isArrived ? "fill-emerald-400 stroke-emerald-500" :
                    isLoading ? "fill-amber-400 stroke-amber-500" : "fill-indigo-400 stroke-indigo-600"
                  } stroke-2`}
                />
                <g className="opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none">
                  <rect
                    x={x - 70}
                    y={y - 50}
                    width="140"
                    height="42"
                    rx="6"
                    fill="#070a13"
                    stroke="#312e81"
                    strokeWidth="1"
                    className="shadow-xl"
                  />
                  <text x={x} y={y - 38} textAnchor="middle" fill="#ffffff" className="text-[9px] font-black font-sans">
                    {order.vehicle}
                  </text>
                  <text x={x} y={y - 26} textAnchor="middle" fill="#94a3b8" className="text-[8px] font-mono">
                    {order.driverName}
                  </text>
                  <text x={x} y={y - 14} textAnchor="middle" fill="#818cf8" className="text-[8px] font-mono">
                    {order.speed > 0 ? `${order.speed} км/с | ${order.progress}%` : `${order.status} (${order.progress}%)`}
                  </text>
                </g>
                <title>{`${order.vehicle} (${order.driverName})\nҲолат: ${order.status}\nТезлик: ${order.speed} км/с\nЖараён: ${order.progress}%\nЮк: ${order.material}`}</title>
              </g>
            );
          })}
        </svg>
      </div>
    </div>
  );
}
