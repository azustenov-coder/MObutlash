import { TransportOrder } from "../../types";
import { getDestKey } from "../../utils/mapUtils";

interface OperationsTableProps {
  transportOrders: TransportOrder[];
  mapPoints: Record<string, { x: number; y: number; label: string }>;
}

export function OperationsTable({ transportOrders, mapPoints }: OperationsTableProps) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse" />
          <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
            Tizimdagi Avtomobillar Ro'yxati va GPS Nazorati
          </h3>
        </div>
        <span className="text-xs font-mono font-bold text-slate-300 bg-slate-950 px-3 py-1 rounded-md border border-slate-800">
          AVTOPARK MONITORI
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-mono font-bold text-xs uppercase tracking-wider">
              <th className="py-3 px-1">ID</th>
              <th className="py-3 px-2">Texnika / Haydovchi</th>
              <th className="py-3 px-2">GPS / Tezlik</th>
              <th className="py-3 px-2">Marshrut</th>
              <th className="py-3 px-2 text-right">Progress</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/40">
            {transportOrders.map((order, idx) => (
              <tr key={idx} className="hover:bg-slate-900/40 transition duration-150">
                <td className="py-4 px-1 font-mono font-bold text-indigo-400 text-sm">{order.id}</td>
                <td className="py-4 px-2">
                  <p className="font-extrabold text-slate-100 text-sm">{order.vehicle}</p>
                  <p className="text-xs text-slate-400 font-mono font-medium">{order.driverName}</p>
                </td>
                <td className="py-4 px-2 space-y-1">
                  <div className="flex items-center space-x-1.5">
                    <span className={`h-2 w-2 rounded-full ${
                      order.gpsStatus === "Faol" ? "bg-emerald-400 animate-pulse" :
                      order.gpsStatus === "Yuklanmoqda" ? "bg-amber-400 animate-pulse" : "bg-slate-500"
                    }`} />
                    <span className="text-xs font-mono font-bold text-slate-300">
                      {order.gpsStatus === "Faol" ? "Faol" : order.gpsStatus === "Yuklanmoqda" ? "Yuklanmoqda" : "Oflayn"}
                    </span>
                  </div>
                  {order.speed > 0 ? (
                    <p className="text-[10px] font-mono font-bold text-indigo-400 bg-indigo-500/5 border border-indigo-500/10 px-1.5 py-0.5 rounded inline-block">
                      {order.speed} km/s
                    </p>
                  ) : (
                    <p className="text-[10px] text-slate-500 font-mono">To'xtagan</p>
                  )}
                </td>
                <td className="py-4 px-2">
                  <p className="text-sm font-semibold text-slate-200">
                    Ombor ➔ {getDestKey(order.destination) && mapPoints[getDestKey(order.destination)!] ? mapPoints[getDestKey(order.destination)!].label : order.destination.split(" ")[0]}
                  </p>
                  <p className="text-xs text-slate-400 font-mono truncate max-w-[150px]" title={order.material}>
                    Yuk: {order.material} ({order.quantity})
                  </p>
                </td>
                <td className="py-4 px-2 text-right space-y-1.5">
                  <div className="flex items-center justify-end space-x-2 font-mono text-xs font-bold text-slate-200">
                    <span>{order.status}</span>
                    <span>({order.progress}%)</span>
                  </div>
                  
                  <div className="w-28 h-2 bg-slate-950 rounded-full overflow-hidden inline-block border border-slate-800">
                    <div 
                      className={`h-full rounded-full ${
                        order.status === "Етказилди" ? "bg-emerald-500" :
                        order.status === "Йўлда" ? "bg-blue-500" : "bg-amber-500"
                      }`}
                      style={{ width: `${order.progress}%` }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
