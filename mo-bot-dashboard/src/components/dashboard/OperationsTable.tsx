import { Vehicle } from "../../types";

interface OperationsTableProps {
  vehicles: Vehicle[];
}

export function OperationsTable({ vehicles }: OperationsTableProps) {
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-4 sm:p-6 shadow-2xl flex flex-col gap-5 h-[700px] lg:h-[1022px]">
      <div className="shrink-0 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div className="flex items-center space-x-2">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-400 animate-pulse" />
          <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
            Тизимдаги автомобиллар рўйхати ва GPS назорати
          </h3>
        </div>
        <span className="self-start sm:self-auto text-xs font-mono font-bold text-slate-300 bg-slate-950 px-3 py-1 rounded-md border border-slate-800">
          АВТОПАРК МОНИТОРИНГИ
        </span>
      </div>

      <div className="flex-1 min-h-0 overflow-auto dashboard-scrollbar pb-2 pr-1">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-mono font-bold text-xs uppercase tracking-wider">
              <th className="py-3 px-1">Т/р</th>
              <th className="py-3 px-2">Техника / Ҳайдовчи</th>
              <th className="py-3 px-2">GPS / Тезлик</th>
              <th className="py-3 px-2">Телефон / Модель</th>
              <th className="py-3 px-2 text-right">Ҳолат</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/40">
            {vehicles.map((vehicle, idx) => (
              <tr key={vehicle.name} className="hover:bg-slate-900/40 transition duration-150">
                <td className="py-4 px-1 font-mono font-bold text-indigo-400 text-sm">{idx + 1}</td>
                <td className="py-4 px-2">
                  <p className="font-extrabold text-slate-100 text-sm">{vehicle.name}</p>
                  <p className="text-xs text-slate-400 font-mono font-medium">{vehicle.driverName}</p>
                </td>
                <td className="py-4 px-2 space-y-1">
                  <div className="flex items-center space-x-1.5">
                    <span className="h-2 w-2 rounded-full bg-slate-500" />
                    <span className="text-xs font-mono font-bold text-slate-400">GPS уланмаган</span>
                  </div>
                  <p className="text-[10px] text-slate-500 font-mono">Тезлик мавжуд эмас</p>
                </td>
                <td className="py-4 px-2">
                  <p className="text-sm font-semibold text-slate-200">{vehicle.driverPhone}</p>
                  <p className="text-xs text-slate-400 font-mono">{vehicle.model}</p>
                </td>
                <td className="py-4 px-2 text-right">
                  <span className={`inline-block px-2.5 py-1 rounded-md text-xs font-black border ${vehicle.status === "Соз" ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" : "text-red-400 bg-red-500/10 border-red-500/20"}`}>
                    {vehicle.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
