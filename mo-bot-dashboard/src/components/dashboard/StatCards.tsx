import { Bot, TrendingUp, Truck, Radio, Wrench, CheckCircle2, AlertTriangle, AlertCircle } from "lucide-react";
import { DashboardStats } from "../../types";

interface StatCardsProps {
  stats: DashboardStats;
}

export function StatCards({ stats }: StatCardsProps) {
  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      
      {/* Card 1: Bot Actions */}
      <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-indigo-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
        <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
          <Bot className="w-32 h-32 text-indigo-400" />
        </div>
        <div className="p-3.5 bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400 shadow-inner shrink-0">
          <Bot className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Жами Бот Амаллари</p>
          <h3 className="text-3xl font-black text-white mt-1 font-mono">{stats.totalLogsCount}</h3>
          <p className="text-xs text-emerald-400 font-bold mt-1.5 flex items-center">
            <TrendingUp className="w-4 h-4 mr-1 shrink-0" /> +28% Фаоллик (Бугун)
          </p>
        </div>
      </div>

      {/* Card 2: Pending Orders */}
      <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-blue-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
        <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
          <Truck className="w-32 h-32 text-blue-400" />
        </div>
        <div className="p-3.5 bg-blue-500/10 rounded-xl border border-blue-500/20 text-blue-400 shadow-inner shrink-0">
          <Truck className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Йўлдаги Юклар</p>
          <h3 className="text-3xl font-black text-white mt-1 font-mono">{stats.pendingOrdersCount}</h3>
          <p className="text-xs text-blue-300 font-bold mt-1.5 flex items-center">
            <Radio className="w-4 h-4 mr-1 animate-pulse text-blue-400 shrink-0" /> Маршрутлар Назоратда
          </p>
        </div>
      </div>

      {/* Card 3: Active Vehicles */}
      <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-emerald-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
        <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
          <Wrench className="w-32 h-32 text-emerald-400" />
        </div>
        <div className="p-3.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400 shadow-inner shrink-0">
          <Wrench className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Соз Техникалар</p>
          <h3 className="text-3xl font-black text-white mt-1 font-mono">{stats.activeVehiclesCount}</h3>
          <p className="text-xs text-emerald-400 font-bold mt-1.5 flex items-center">
            <CheckCircle2 className="w-4 h-4 mr-1 shrink-0" /> 82% Техник Тайёрлик
          </p>
        </div>
      </div>

      {/* Card 4: Critical Materials */}
      <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-amber-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
        <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
          <AlertTriangle className="w-32 h-32 text-amber-400" />
        </div>
        <div className="p-3.5 bg-amber-500/10 rounded-xl border border-amber-500/20 text-amber-400 shadow-inner shrink-0">
          <AlertTriangle className="w-6 h-6" />
        </div>
        <div>
          <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Критик Материаллар</p>
          <h3 className="text-3xl font-black text-white mt-1 font-mono">{stats.criticalMaterialsCount}</h3>
          <p className="text-xs text-amber-400 font-bold mt-1.5 flex items-center">
            <AlertCircle className="w-4 h-4 mr-1 shrink-0 text-amber-400 animate-pulse" /> Захирани Тўлдириш Шарт
          </p>
        </div>
      </div>

    </section>
  );
}
