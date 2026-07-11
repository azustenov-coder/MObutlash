import { useState, useEffect, useRef } from "react";
import { 
  Shield, 
  Bot, 
  TrendingUp, 
  AlertTriangle, 
  Truck, 
  Wrench, 
  Package, 
  Clock, 
  Play, 
  CheckCircle2, 
  User, 
  RefreshCw, 
  Search, 
  Sparkles, 
  Radio, 
  Layers, 
  History,
  FileSpreadsheet,
  AlertCircle,
  Fingerprint,
  Settings
} from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { DashboardState, BotEvent } from "./types";

export default function App() {
  const [data, setData] = useState<DashboardState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"barchasi" | "boshqaruvchi" | "mexanik" | "brigadir" | "br" | "yetkazib_beruvchi" | "skladchik">("barchasi");
  const [rightTab, setRightTab] = useState<"operatsiyalar" | "davomat">("operatsiyalar");
  const [searchQuery, setSearchQuery] = useState("");
  const [newEventId, setNewEventId] = useState<string | null>(null);
  const [triggeringSim, setTriggeringSim] = useState(false);

  const [selectedMap, setSelectedMap] = useState<"yangiyol" | "toshkent">("yangiyol");

  // GPS Map Coordinates mapping
  const yangiyolPoints: Record<string, { x: number; y: number; label: string }> = {
    sklad: { x: 300, y: 170, label: "Ombor (Sklad-1)" },
    tinchlik: { x: 180, y: 290, label: "Tinchlik MFY" },
    navruz: { x: 80, y: 210, label: "Navro'z MFY" },
    gulbahor: { x: 480, y: 60, label: "Gulbahor Qo'rg'oni" },
    niyozbosh: { x: 200, y: 90, label: "Niyozbosh" },
    binokor: { x: 280, y: 40, label: "Binokor MFY" },
    vokzal: { x: 350, y: 130, label: "Yangiyo'l Vokzal" }
  };

  const toshkentPoints: Record<string, { x: number; y: number; label: string }> = {
    sklad: { x: 300, y: 170, label: "Ombor (Sklad-1)" },
    sergeli: { x: 180, y: 290, label: "Sergeli-5" },
    chilonzor: { x: 80, y: 210, label: "Chilonzor 9" },
    yunusobod: { x: 480, y: 60, label: "Yunusobod 12" },
    olmazor: { x: 200, y: 90, label: "Olmazor Res." },
    qoraqamish: { x: 280, y: 40, label: "Qoraqamish-3" },
    city: { x: 350, y: 130, label: "Tashkent City" }
  };

  const mapPoints = selectedMap === "yangiyol" ? yangiyolPoints : toshkentPoints;

  const getDestKey = (dest: string) => {
    const d = dest.toLowerCase();
    // Yangiyol keys
    if (d.includes("tinchlik")) return "tinchlik";
    if (d.includes("navr") || d.includes("навр")) return "navruz";
    if (d.includes("gulbahor") || d.includes("гулбаҳор")) return "gulbahor";
    if (d.includes("niyozbosh") || d.includes("ниёзбош")) return "niyozbosh";
    if (d.includes("binokor") || d.includes("бинокор")) return "binokor";
    if (d.includes("vokzal") || d.includes("вокзал")) return "vokzal";
    // Tashkent keys
    if (d.includes("sergeli") || d.includes("сергели")) return "sergeli";
    if (d.includes("chilonzor") || d.includes("чилонзор")) return "chilonzor";
    if (d.includes("yunusobod") || d.includes("юнусобод")) return "yunusobod";
    if (d.includes("olmazor") || d.includes("олмазор")) return "olmazor";
    if (d.includes("qoraqamish") || d.includes("қорақамиш")) return "qoraqamish";
    if (d.includes("city") || d.includes("сити")) return "city";
    return null;
  };
  
  // Gemini AI state
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState<string | null>(null);

  // Time tracker
  const [currentTime, setCurrentTime] = useState("");

  // Load initial state
  const fetchState = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    try {
      const response = await fetch("/api/state");
      if (!response.ok) throw new Error("Сервердан маълумот олишда хатолик");
      const stateData = await response.json();
      setData(stateData);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError("Уланишда хатолик юз берди. Илтимос, сервер ишга тушишини кутинг.");
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  useEffect(() => {
    fetchState(true);

    const updateTime = () => {
      const now = new Date();
      setCurrentTime(now.toLocaleTimeString("uz-UZ", { hour12: false }));
    };
    updateTime();
    const clockInterval = setInterval(updateTime, 1000);

    // Live GPS polling interval
    const pollInterval = setInterval(() => {
      fetchState(false);
    }, 4000);

    // Establish Server-Sent Events (SSE) for Real-time Bot logs
    const eventSource = new EventSource("/api/events");
    
    eventSource.onmessage = (event) => {
      try {
        const newEvent: BotEvent = JSON.parse(event.data);
        setNewEventId(newEvent.id);
        setTimeout(() => setNewEventId(null), 4000);
        fetchState(false);
      } catch (e) {
        console.error("SSE parse error", e);
      }
    };

    return () => {
      eventSource.close();
      clearInterval(clockInterval);
      clearInterval(pollInterval);
    };
  }, []);

  // Manual Simulation Trigger
  const handleTriggerSimulation = async () => {
    setTriggeringSim(true);
    try {
      const response = await fetch("/api/trigger-simulation", { method: "POST" });
      if (response.ok) {
        await fetchState(false);
      }
    } catch (err) {
      console.error("Simulation trigger failed", err);
    } finally {
      setTriggeringSim(false);
    }
  };

  // Run AI Audit on logs using Gemini
  const handleAiAudit = async () => {
    setAiLoading(true);
    setAiError(null);
    setAiAnalysis(null);
    try {
      const response = await fetch("/api/gemini/analyze", { method: "POST" });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || "Сунъий интеллект хизмати фаол эмас");
      }
      setAiAnalysis(result.analysis);
    } catch (err: any) {
      console.error(err);
      setAiError(err.message || "Хатолик юз берdi. Gemini API калити тўғри ўрнатилганлигини текширинг.");
    } finally {
      setAiLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#070b13] text-slate-100 flex flex-col items-center justify-center p-6 font-sans">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(79,70,229,0.08),transparent_70%)] pointer-events-none" />
        <div className="relative flex flex-col items-center max-w-sm text-center">
          <div className="p-4 bg-indigo-500/10 rounded-2xl border border-indigo-500/20 mb-6 animate-bounce">
            <Bot className="w-12 h-12 text-indigo-400" />
          </div>
          <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin mb-4"></div>
          <p className="text-white font-mono text-base font-semibold tracking-wide">ТИЗИМ ЮКЛАНМОҚДА</p>
          <p className="text-sm text-indigo-300 mt-2 font-mono">МО Бот реал вақтдаги бошқарув консоли уланмоқда...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-[#070b13] text-slate-100 flex flex-col items-center justify-center p-6 font-sans">
        <div className="bg-slate-900/80 border border-red-500/30 rounded-2xl p-8 max-w-md w-full text-center shadow-2xl relative">
          <div className="p-3 bg-red-500/10 rounded-xl inline-block mb-4 border border-red-500/20">
            <AlertCircle className="w-10 h-10 text-red-400" />
          </div>
          <h2 className="text-xl font-bold mb-3 text-white">Тармоққа уланиш хатоси</h2>
          <p className="text-slate-300 text-sm leading-relaxed mb-6">{error || "Сервер маълумотлари юкланмади."}</p>
          <button 
            onClick={() => fetchState(true)}
            className="w-full bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white font-semibold py-3 px-4 rounded-xl transition duration-150 flex items-center justify-center space-x-2 shadow-lg shadow-indigo-600/25 cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
            <span>Қайта юклаш</span>
          </button>
        </div>
      </div>
    );
  }

  const filteredLogs = data.logs.filter((log) => {
    const matchesTab = activeTab === "barchasi" || log.role === activeTab;
    const searchLower = searchQuery.toLowerCase();
    return matchesTab && (
      log.fullName.toLowerCase().includes(searchLower) ||
      log.username.toLowerCase().includes(searchLower) ||
      log.action.toLowerCase().includes(searchLower) ||
      log.details.toLowerCase().includes(searchLower)
    );
  });

  const roleCounts = data.logs.reduce((acc, log) => {
    acc[log.role] = (acc[log.role] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const rolesList = [
    { key: "boshqaruvchi", label: "Бошқарувчи (Менеджер)", color: "#a78bfa", bg: "bg-violet-500/10", border: "border-violet-500/30" },
    { key: "br", label: "БР Оператори", color: "#60a5fa", bg: "bg-blue-500/10", border: "border-blue-500/30" },
    { key: "brigadir", label: "Бригадир (Усталар)", color: "#34d399", bg: "bg-emerald-500/10", border: "border-emerald-500/30" },
    { key: "skladchik", label: "Омборчи (Склад)", color: "#fbbf24", bg: "bg-amber-500/10", border: "border-amber-500/30" },
    { key: "yetkazib_beruvchi", label: "Таъминотчи", color: "#f97316", bg: "bg-orange-500/10", border: "border-orange-500/30" },
    { key: "mexanik", label: "Механик (Гараж)", color: "#f87171", bg: "bg-red-500/10", border: "border-red-500/30" }
  ];

  const maxRoleActivity = Math.max(...rolesList.map(r => roleCounts[r.key] || 0), 1);

  const roleMeta = {
    boshqaruvchi: { label: "Бошқарувчи", color: "text-violet-400 bg-violet-400/10 border-violet-400/20", icon: Shield },
    br: { label: "БР Оператори", color: "text-blue-400 bg-blue-400/10 border-blue-400/20", icon: Layers },
    brigadir: { label: "Бригадир", color: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20", icon: User },
    skladchik: { label: "Омборчи", color: "text-amber-400 bg-amber-400/10 border-amber-400/20", icon: Package },
    yetkazib_beruvchi: { label: "Таъминотчи", color: "text-orange-400 bg-orange-400/10 border-orange-400/20", icon: Truck },
    mexanik: { label: "Механик", color: "text-red-400 bg-red-400/10 border-red-400/20", icon: Wrench },
  };

  return (
    <div id="main_dashboard_layout" className="min-h-screen bg-[#070913] text-slate-100 font-sans selection:bg-indigo-600 selection:text-white pb-12">
      {/* Decorative cyber grid overlay */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#0f172a_1px,transparent_1px),linear-gradient(to_bottom,#0f172a_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none opacity-40" />

      {/* 1. Header Area with glowing neon and bold visual impact */}
      <header className="sticky top-0 z-40 bg-[#070913]/90 backdrop-blur-xl border-b border-slate-800/80 px-4 py-4 lg:px-8">
        <div className="max-w-7xl mx-auto flex flex-col lg:flex-row items-center justify-between gap-4">
          
          <div className="flex items-center space-x-4">
            <div className="p-3 bg-gradient-to-br from-indigo-500/20 to-indigo-600/10 rounded-xl border border-indigo-500/30 shadow-lg shadow-indigo-500/5">
              <Bot className="w-8 h-8 text-indigo-400" />
            </div>
            <div>
              <div className="flex items-center space-x-3">
                <h1 className="text-xl lg:text-2xl font-extrabold tracking-tight text-white font-sans">
                  МО БОТ <span className="bg-gradient-to-r from-indigo-400 to-indigo-600 bg-clip-text text-transparent">ДАШБОРДИ</span>
                </h1>
                <span className="text-xs bg-indigo-500/10 border border-indigo-500/30 text-indigo-300 px-2.5 py-0.5 rounded-full font-mono font-bold tracking-wider">
                  СУПЕР АДМИН ПАНЕЛИ
                </span>
              </div>
              <p className="text-sm text-slate-400 mt-0.5 font-medium">Моддий-техника таъминоти Телеграм боти реал вақтдаги мониторинги ва назорати</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto justify-end">
            {/* Real-time pulse indicator */}
            <div className="flex items-center space-x-2.5 bg-slate-900/90 px-4 py-2.5 rounded-xl border border-slate-800 text-sm text-slate-200 font-mono font-medium shadow-inner">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
              <span>ЖОНЛИ РЕЖИМ</span>
            </div>

            {/* Time Zone */}
            <div className="hidden sm:flex items-center space-x-2 bg-slate-900/90 px-4 py-2.5 rounded-xl border border-slate-800 text-sm text-slate-200 font-mono shadow-inner">
              <Clock className="w-4 h-4 text-indigo-400" />
              <span className="font-bold">{currentTime || "00:00:00"}</span>
            </div>

            {/* Bot manual stimulation */}
            <button
              onClick={handleTriggerSimulation}
              disabled={triggeringSim}
              className="bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl transition duration-150 flex items-center space-x-2 disabled:opacity-50 cursor-pointer shadow-lg shadow-indigo-600/30 border border-indigo-400/30"
              title="Телеграм ботдан келадиган сўровни қўлда симуляция қилиш"
            >
              <Play className={`w-4 h-4 fill-current ${triggeringSim ? "animate-spin" : ""}`} />
              <span>{triggeringSim ? "Симуляция..." : "Бот Симуляцияси"}</span>
            </button>

            {/* Excel Download button with bold visual */}
            <a
              href="/api/download-report"
              className="bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 text-white text-sm font-bold px-4 py-2.5 rounded-xl transition duration-150 flex items-center space-x-2 shadow-lg shadow-emerald-600/30 border border-emerald-500/30"
              title="Кунлик тўлиқ ҳисоботни юклаб олиш"
            >
              <FileSpreadsheet className="w-4 h-4" />
              <span>Эхcел Ҳисоботи</span>
            </a>
          </div>

        </div>
      </header>

      <main id="dashboard_content_stage" className="max-w-7xl mx-auto px-4 py-6 lg:px-8 space-y-8">
        
        {/* 2. KPI metrics grid with larger and highly legible typography */}
        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          
          <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-indigo-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
            <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <Bot className="w-32 h-32 text-indigo-400" />
            </div>
            <div className="p-3.5 bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400 shadow-inner shrink-0">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Жами Бот Амаллари</p>
              <h3 className="text-3xl font-black text-white mt-1 font-mono">{data.stats.totalLogsCount}</h3>
              <p className="text-xs text-emerald-400 font-bold mt-1.5 flex items-center">
                <TrendingUp className="w-4 h-4 mr-1 shrink-0" /> +28% Фаоллик (Бугун)
              </p>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-blue-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
            <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <Truck className="w-32 h-32 text-blue-400" />
            </div>
            <div className="p-3.5 bg-blue-500/10 rounded-xl border border-blue-500/20 text-blue-400 shadow-inner shrink-0">
              <Truck className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Йўлдаги Юклар</p>
              <h3 className="text-3xl font-black text-white mt-1 font-mono">{data.stats.pendingOrdersCount}</h3>
              <p className="text-xs text-blue-300 font-bold mt-1.5 flex items-center">
                <Radio className="w-4 h-4 mr-1 animate-pulse text-blue-400 shrink-0" /> Маршрутлар Назоратда
              </p>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-emerald-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
            <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <Wrench className="w-32 h-32 text-emerald-400" />
            </div>
            <div className="p-3.5 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400 shadow-inner shrink-0">
              <Wrench className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Соз Техникалар</p>
              <h3 className="text-3xl font-black text-white mt-1 font-mono">{data.stats.activeVehiclesCount}</h3>
              <p className="text-xs text-emerald-400 font-bold mt-1.5 flex items-center">
                <CheckCircle2 className="w-4 h-4 mr-1 shrink-0" /> 82% Техник Тайёрлик
              </p>
            </div>
          </div>

          <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 hover:border-amber-500/40 rounded-2xl p-6 flex items-start space-x-5 transition duration-200 shadow-xl relative overflow-hidden group">
            <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
              <AlertTriangle className="w-32 h-32 text-amber-400" />
            </div>
            <div className="p-3.5 bg-amber-500/10 rounded-xl border border-amber-500/20 text-amber-400 shadow-inner shrink-0">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">Критик Материаллар</p>
              <h3 className="text-3xl font-black text-white mt-1 font-mono">{data.stats.criticalMaterialsCount}</h3>
              <p className="text-xs text-amber-400 font-bold mt-1.5 flex items-center">
                <AlertCircle className="w-4 h-4 mr-1 shrink-0 text-amber-400 animate-pulse" /> Захирани Тўлдириш Шарт
              </p>
            </div>
          </div>

        </section>

        {/* 3. Central Analysis Diagrams Row - High Craft Custom Visualizations with Bold fonts */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Chart A: Ombor Zaxiralari (Professional Stock Card) */}
          <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
                  <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
                    Омбор Моддий Захиралари ва Лимитлар
                  </h3>
                </div>
                <span className="text-xs text-slate-400 font-mono font-bold bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
                  МАРКАЗИЙ СКЛАД-1
                </span>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed mb-6">
                Материалларнинг жорий қолдиғи (рангли барлар) ва тизимда созланган минимал захира лимитлари (вертикал қизил чизиқ).
              </p>
            </div>

            {/* Custom Responsive Stock Bar Chart */}
            <div className="space-y-6">
              {/* Group 1: Finished Goods */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2 border-b border-slate-800/80 pb-2">
                  <Package className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-mono font-bold text-emerald-400 uppercase tracking-wider">
                    Тайёр маҳсулотлар (1-бўлим)
                  </span>
                </div>
                {data.inventory
                  .filter(item => item.category === "Тайёр маҳсулот" || item.category === "tayyor")
                  .map((item, idx) => {
                    let maxCap = 250;
                    if (item.name.includes("плиткаси")) maxCap = 1000;
                    if (item.name.includes("блоки")) maxCap = 200;
                    if (item.name.includes("бордюри")) maxCap = 150;
                    
                    const percentage = Math.min(100, (item.quantity / maxCap) * 100);
                    const limitPercentage = (item.minThreshold / maxCap) * 100;
                    
                    return (
                      <div key={idx} className="space-y-1.5">
                        <div className="flex items-center justify-between text-sm font-sans font-medium">
                          <span className="text-slate-100 font-bold text-sm lg:text-base">{item.name}</span>
                          <div className="flex items-center space-x-3">
                            <span className="text-slate-300 font-mono text-xs font-bold">
                              {item.quantity.toLocaleString()} / {maxCap.toLocaleString()} {item.unit}
                            </span>
                            <span className={`px-2.5 py-0.5 rounded-md text-xs font-black tracking-wide ${
                              item.status === "Нормал" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                              item.status === "Кам қолди" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" : 
                              "bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse"
                            }`}>
                              {item.status.toUpperCase()}
                            </span>
                          </div>
                        </div>
                        
                        <div className="h-5 w-full bg-slate-950 rounded-lg overflow-hidden relative border border-slate-800/80 p-0.5">
                          <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ duration: 0.8, ease: "easeOut" }}
                            className={`h-full rounded-md relative ${
                              item.status === "Нормал" ? "bg-gradient-to-r from-emerald-600 to-emerald-400" :
                              item.status === "Кам қолди" ? "bg-gradient-to-r from-amber-500 to-amber-300" : 
                              "bg-gradient-to-r from-red-600 to-red-400"
                            }`}
                          >
                            <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.15),transparent_60%)]" />
                          </motion.div>
                          
                          <div 
                            className="absolute top-0 bottom-0 w-1 bg-red-400 z-10 shadow-[0_0_8px_rgba(239,68,68,0.5)]" 
                            style={{ left: `${limitPercentage}%` }}
                            title={`Минимал хавфсиз захира: ${item.minThreshold}`}
                          >
                            <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-[9px] text-red-400 font-mono font-bold bg-[#070913] px-1 py-0.2 rounded border border-red-500/20 leading-none">
                              лимит
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>

              {/* Group 2: Components / Materials */}
              <div className="space-y-4 pt-2">
                <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
                  <Settings className="w-4 h-4 text-indigo-400" />
                  <span className="text-xs font-mono font-bold text-indigo-400 uppercase tracking-wider">
                    Бутловчи маҳсулотлар (2-бўлим)
                  </span>
                </div>
                {data.inventory
                  .filter(item => item.category !== "Тайёр маҳсулот" && item.category !== "tayyor")
                  .map((item, idx) => {
                    let maxCap = 250;
                    if (item.name.includes("Ғишт")) maxCap = 100000;
                    if (item.name.toLowerCase().includes("ёқилғи")) maxCap = 3000;
                    if (item.name.includes("Цемент")) maxCap = 300;
                    
                    const percentage = Math.min(100, (item.quantity / maxCap) * 100);
                    const limitPercentage = (item.minThreshold / maxCap) * 100;
                    
                    return (
                      <div key={idx} className="space-y-1.5">
                        <div className="flex items-center justify-between text-sm font-sans font-medium">
                          <span className="text-slate-100 font-bold text-sm lg:text-base">{item.name}</span>
                          <div className="flex items-center space-x-3">
                            <span className="text-slate-300 font-mono text-xs font-bold">
                              {item.quantity.toLocaleString()} / {maxCap.toLocaleString()} {item.unit}
                            </span>
                            <span className={`px-2.5 py-0.5 rounded-md text-xs font-black tracking-wide ${
                              item.status === "Нормал" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                              item.status === "Кам қолди" ? "bg-amber-500/10 text-amber-400 border border-emerald-500/20" : 
                              "bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse"
                            }`}>
                              {item.status.toUpperCase()}
                            </span>
                          </div>
                        </div>
                        
                        <div className="h-5 w-full bg-slate-950 rounded-lg overflow-hidden relative border border-slate-800/80 p-0.5">
                          <motion.div 
                            initial={{ width: 0 }}
                            animate={{ width: `${percentage}%` }}
                            transition={{ duration: 0.8, ease: "easeOut" }}
                            className={`h-full rounded-md relative ${
                              item.status === "Нормал" ? "bg-gradient-to-r from-emerald-600 to-emerald-400" :
                              item.status === "Кам қолди" ? "bg-gradient-to-r from-amber-500 to-amber-300" : 
                              "bg-gradient-to-r from-red-600 to-red-400"
                            }`}
                          >
                            <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.15),transparent_60%)]" />
                          </motion.div>
                          
                          <div 
                            className="absolute top-0 bottom-0 w-1 bg-red-400 z-10 shadow-[0_0_8px_rgba(239,68,68,0.5)]" 
                            style={{ left: `${limitPercentage}%` }}
                            title={`Минимал хавфсиз захира: ${item.minThreshold}`}
                          >
                            <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-[9px] text-red-400 font-mono font-bold bg-[#070913] px-1 py-0.2 rounded border border-red-500/20 leading-none">
                              лимит
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
              </div>
            </div>
          </div>

          {/* Chart B: Roles Activity count & custom radar/bar concept */}
          <div className="lg:col-span-5 bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-2">
                  <div className="w-2.5 h-2.5 rounded-full bg-indigo-400 animate-pulse" />
                  <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
                    Роллар Бўйича Фаоллик
                  </h3>
                </div>
                <span className="text-xs text-slate-400 font-mono font-bold bg-slate-950 px-2.5 py-1 rounded-md border border-slate-800">
                  БУГУНГИ СТАТИСТИКА
                </span>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed mb-4">
                Ҳар бир масъул ходим гуруҳининг бугунги кунда Телеграм боти орқали жўнатган умумий сўровлари ва ҳисоботлари сони.
              </p>
            </div>

            {/* Custom SVG Column bar charts for aesthetic layout */}
            <div className="flex items-end justify-between h-56 px-4 pt-8 pb-4 border border-slate-800/60 rounded-xl bg-slate-950/50">
              {rolesList.map((role, idx) => {
                const count = roleCounts[role.key] || 0;
                const heightPercent = Math.max(12, (count / maxRoleActivity) * 100);
                
                return (
                  <div key={idx} className="flex flex-col items-center flex-1 space-y-3 group relative">
                    
                    {/* Permanent/Hover Counter Badge - Highly readable */}
                    <div className="bg-slate-900 border border-slate-800 rounded-md px-2 py-0.5 text-xs font-mono font-bold text-white shadow-lg -translate-y-1">
                      {count} та
                    </div>

                    {/* SVG column bar */}
                    <div className="w-10 bg-slate-950 rounded-lg h-32 flex items-end overflow-hidden relative border border-slate-800">
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${heightPercent}%` }}
                        transition={{ duration: 1, delay: idx * 0.05 }}
                        className="w-full rounded-t-md relative"
                        style={{ backgroundColor: role.color }}
                      >
                        {/* Glow overlay inside column */}
                        <div className="w-full h-full bg-gradient-to-t from-black/30 to-white/10" />
                        
                        {/* Hover shine */}
                        <div className="absolute inset-0 bg-white/15 opacity-0 group-hover:opacity-100 transition-opacity duration-150" />
                      </motion.div>
                    </div>

                    {/* Label */}
                    <span className="text-xs font-mono text-slate-300 font-bold text-center uppercase tracking-tight block truncate w-16" title={role.label}>
                      {role.key === "boshqaruvchi" ? "Админ" : 
                       role.key === "br" ? "Оператор" : 
                       role.key === "brigadir" ? "Бригадир" : 
                       role.key === "skladchik" ? "Омбор" : 
                       role.key === "yetkazib_beruvchi" ? "Таъминотчи" : "Механик"}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Total distribution explanation */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4 text-xs font-mono text-slate-300 font-medium">
              {rolesList.map((role) => (
                <div key={role.key} className="flex items-center space-x-2">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: role.color }} />
                  <span className="truncate">{role.label.split(" ")[0]}</span>
                </div>
              ))}
            </div>
          </div>

        </section>

        {/* 4. Gemini AI Auditor Section with Premium Output & Font Adjustments */}
        <section className="bg-gradient-to-br from-indigo-950/30 via-indigo-900/10 to-slate-950/90 border border-indigo-500/20 rounded-2xl p-6 lg:p-8 relative overflow-hidden shadow-2xl">
          
          {/* Cyber light beam */}
          <div className="absolute top-0 right-1/4 w-96 h-96 bg-indigo-500/5 rounded-full blur-3xl pointer-events-none" />

          <div className="relative z-10 flex flex-col lg:flex-row items-start justify-between gap-6">
            
            <div className="space-y-3 max-w-3xl">
              <div className="flex items-center space-x-2">
                <Sparkles className="w-6 h-6 text-indigo-400 animate-pulse shrink-0" />
                <span className="text-xs font-black font-mono tracking-widest text-indigo-300 uppercase">
                  GEMINI АИ КЎМАКЧИ АУДИТИ
                </span>
              </div>
              <h2 className="text-xl lg:text-2xl font-black text-white tracking-tight">
                Кунlik Ҳисобот ва Интеллектуал Таҳлил
              </h2>
              <p className="text-slate-300 text-sm lg:text-base leading-relaxed">
                Тизимдаги барча логларни, омбор қолдиғини, ҳайдовчилар етказиб бериш жараёнларини ва носоз махсус техникалар ҳолатларини Gemini АИ орқали тўлиқ аудит қилинг. Хато-камчиликлар ва самарадорликни ошириш учун тавсиялар олинг.
              </p>
            </div>

            <div className="w-full lg:w-auto self-center shrink-0">
              <button
                onClick={handleAiAudit}
                disabled={aiLoading}
                className="w-full lg:w-auto bg-gradient-to-r from-indigo-600 via-indigo-500 to-violet-600 hover:from-indigo-500 hover:to-violet-500 active:from-indigo-700 active:to-violet-700 text-white font-bold text-sm px-6 py-4 rounded-xl transition duration-150 flex items-center justify-center space-x-2.5 shadow-xl shadow-indigo-600/30 cursor-pointer disabled:opacity-50 border border-indigo-400/30"
              >
                {aiLoading ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    <span>Маълумотлар таҳлил қилинмоқда...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-5 h-5 fill-current text-white animate-pulse" />
                    <span>Gemini АИ аудитни ишга тушириш</span>
                  </>
                )}
              </button>
            </div>

          </div>

          {/* AI Result Container */}
          <AnimatePresence>
            {(aiAnalysis || aiLoading || aiError) && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.3 }}
                className="mt-6 border-t border-indigo-500/10 pt-6 relative"
              >
                {aiLoading && (
                  <div className="space-y-4 py-6">
                    <div className="h-5 bg-indigo-500/10 rounded animate-pulse w-3/4"></div>
                    <div className="h-5 bg-indigo-500/10 rounded animate-pulse w-5/6"></div>
                    <div className="h-5 bg-indigo-500/10 rounded animate-pulse w-2/3"></div>
                    <p className="text-center text-sm text-indigo-300 font-mono animate-pulse">
                      Gemini 3.5 реал вақтдаги маълумотларни интеграция қилмоқда...
                    </p>
                  </div>
                )}

                {aiError && (
                  <div className="p-5 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-200 flex items-start space-x-3">
                    <AlertCircle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">АИ таҳлил бажарилмади</p>
                      <p className="mt-1 text-slate-300">{aiError}</p>
                    </div>
                  </div>
                )}

                {aiAnalysis && (
                  <div className="bg-slate-950/90 border border-indigo-500/20 rounded-2xl p-6 lg:p-8 max-h-[500px] overflow-y-auto shadow-2xl relative border border-indigo-500/30 scrollbar-thin">
                    <div className="flex items-center justify-between pb-4 border-b border-indigo-500/20 mb-6">
                      <span className="font-extrabold text-indigo-400 font-sans text-sm lg:text-base flex items-center space-x-2">
                        <Sparkles className="w-5 h-5 text-indigo-400" />
                        <span>КУНЛИК ИНТЕЛЛЕКТУАЛ АУДИТ ҲИСОБОТИ (ЎЗБЕК ТИЛИДА)</span>
                      </span>
                      <span className="text-xs text-slate-500 font-mono font-bold bg-slate-900 px-3 py-1 rounded border border-slate-800">
                        Сана: Бугун
                      </span>
                    </div>
                    
                    {/* Bold, Highly legible typography for report rendering */}
                    <div className="text-slate-200 text-sm lg:text-base leading-relaxed space-y-6 font-sans">
                      {aiAnalysis.split("\n\n").map((paragraph, pIdx) => {
                        // Check if paragraph is a heading or list
                        if (paragraph.trim().startsWith("1.") || paragraph.trim().startsWith("2.") || paragraph.trim().startsWith("3.") || paragraph.trim().startsWith("4.")) {
                          return (
                            <h4 key={pIdx} className="text-base lg:text-lg font-black text-indigo-300 pt-2 flex items-center border-b border-slate-800/60 pb-1.5">
                              {paragraph}
                            </h4>
                          );
                        }
                        if (paragraph.trim().startsWith("-") || paragraph.trim().startsWith("*")) {
                          return (
                            <ul key={pIdx} className="list-disc pl-5 space-y-2 text-slate-300">
                              {paragraph.split("\n").map((li, lIdx) => (
                                <li key={lIdx} className="font-medium text-slate-200">
                                  {li.replace(/^[\s*-]+/, "")}
                                </li>
                              ))}
                            </ul>
                          );
                        }
                        return (
                          <p key={pIdx} className="font-medium text-slate-300 whitespace-pre-line leading-relaxed">
                            {paragraph}
                          </p>
                        );
                      })}
                    </div>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

        </section>

        {/* 5. Core Interface: Real-time activities feed and Tables stage */}
        <section className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          
          {/* Left Column: Real-time activity feeds log (Span 5) */}
          <div className="lg:col-span-5 bg-slate-900/60 border border-slate-800 rounded-2xl p-6 flex flex-col h-[700px] shadow-2xl">
            
            {/* Logs header and search */}
            <div className="space-y-4 mb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <History className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
                    Реал Вақтдаги Бот Фаолият Журнали
                  </h3>
                </div>
                <span className="flex h-3 w-3 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
              </div>

              {/* Roles tab filters - Highly legibile text sizes */}
              <div className="flex flex-wrap gap-2 border-b border-slate-800/80 pb-3">
                <button
                  onClick={() => setActiveTab("barchasi")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition duration-150 cursor-pointer ${
                    activeTab === "barchasi" ? "bg-indigo-600 text-white shadow-lg shadow-indigo-600/20" : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                  }`}
                >
                  Барчаси
                </button>
                {rolesList.map((role) => (
                  <button
                    key={role.key}
                    onClick={() => setActiveTab(role.key as any)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold transition duration-150 cursor-pointer ${
                      activeTab === role.key 
                        ? "bg-indigo-600/25 text-indigo-200 border border-indigo-500/40 shadow-inner" 
                        : "bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800"
                    }`}
                  >
                    {role.key === "boshqaruvchi" ? "Админ" : 
                     role.key === "br" ? "Оператор" : 
                     role.key === "brigadir" ? "Бригадир" : 
                     role.key === "skladchik" ? "Омбор" : 
                     role.key === "yetkazib_beruvchi" ? "Таъминотчи" : "Механик"}
                  </button>
                ))}
              </div>

              {/* Search bar */}
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3.5 top-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Ходим ёки амални қидириш..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-slate-950 text-sm pl-10 pr-4 py-3 rounded-xl border border-slate-800 focus:border-indigo-500/80 focus:outline-none focus:ring-1 focus:ring-indigo-500/40 text-slate-100 font-sans"
                />
              </div>
            </div>

            {/* Scrollable Timeline with improved font sizes */}
            <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin scrollbar-thumb-slate-800">
              <AnimatePresence initial={false}>
                {filteredLogs.length === 0 ? (
                  <div className="text-center py-20 text-slate-500 text-sm font-medium">
                    Қидирувга мос келадиган бот логлари топилмади.
                  </div>
                ) : (
                  filteredLogs.map((log) => {
                    const Meta = roleMeta[log.role] || roleMeta.brigadir;
                    const RoleIcon = Meta.icon;
                    const isNew = newEventId === log.id;
                    
                    return (
                      <motion.div
                        key={log.id}
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ 
                          opacity: 1, 
                          scale: 1,
                          backgroundColor: isNew ? "rgba(79, 70, 229, 0.12)" : "rgba(15, 23, 42, 0.4)"
                        }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.3 }}
                        className={`p-4.5 rounded-2xl border ${
                          isNew ? "border-indigo-500/80 shadow-xl shadow-indigo-600/10" : "border-slate-800/60"
                        } flex items-start space-x-4 transition-all relative`}
                      >
                        {isNew && (
                          <span className="absolute top-3 right-3 flex h-2.5 w-2.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span>
                          </span>
                        )}

                        <div className={`p-3 rounded-xl border shrink-0 ${Meta.color} shadow-inner`}>
                          <RoleIcon className="w-5 h-5" />
                        </div>

                        <div className="flex-1 space-y-2">
                          <div className="flex items-center justify-between">
                            <div>
                              <span className="text-sm lg:text-base font-extrabold text-white">{log.fullName}</span>
                              <span className="text-xs text-indigo-300 font-mono ml-2 font-medium bg-indigo-500/5 px-2 py-0.5 rounded border border-indigo-500/10">
                                {log.username}
                              </span>
                            </div>
                            <span className="text-xs text-indigo-400 font-mono font-bold bg-indigo-500/5 px-2 py-0.5 rounded border border-indigo-500/10">
                              {log.timeFormatted}
                            </span>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`text-[10px] uppercase font-black tracking-widest px-2.5 py-0.5 rounded-full border ${Meta.color}`}>
                              {Meta.label}
                            </span>
                            <span className="text-sm font-black text-slate-100">{log.action}</span>
                          </div>

                          <p className="text-sm text-slate-300 leading-relaxed font-sans font-medium">{log.details}</p>
                          
                          <div className="pt-2 flex items-center justify-between text-xs font-mono text-slate-400 border-t border-slate-800/40">
                            <span className="font-bold">ID: {log.id}</span>
                            <span className={`font-black ${
                              log.status === "Бажарилди" || log.status === "Етказилди" || log.status === "Тасдиқланди" ? "text-emerald-400" :
                              log.status === "Йўлда" || log.status === "Юкланмоқда" ? "text-blue-400" : "text-amber-400"
                            }`}>
                              ● {log.status}
                            </span>
                          </div>
                        </div>
                      </motion.div>
                    );
                  })
                )}
              </AnimatePresence>
            </div>

          </div>

          {/* Right Column: Other Operational Tables (Span 7) */}
          <div className="lg:col-span-7 space-y-8">
            
            {/* Navigation Tabs for Right Column */}
            <div className="flex bg-slate-950 p-1.5 rounded-xl border border-slate-800/80 max-w-sm">
              <button
                onClick={() => setRightTab("operatsiyalar")}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-150 cursor-pointer text-center ${
                  rightTab === "operatsiyalar" ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                Логистика 🚚
              </button>
              <button
                onClick={() => setRightTab("davomat")}
                className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-150 cursor-pointer text-center flex items-center justify-center space-x-1.5 ${
                  rightTab === "davomat" ? "bg-indigo-600 text-white shadow-md shadow-indigo-600/20" : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <Fingerprint className="w-3.5 h-3.5" />
                <span>Ходимлар давомати 👆</span>
              </button>
            </div>

            {rightTab === "operatsiyalar" ? (
              <>
                {/* Table 1: Logistics & Transportation Delivery */}
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
                        {data.transportOrders.map((order, idx) => (
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
                                Ombor ➔ {getDestKey(order.destination) ? mapPoints[getDestKey(order.destination)!].label : order.destination.split(" ")[0]}
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

                {/* GPS Map Component */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                      </span>
                      <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
                        GPS Canli Kuzatuv Xaritasi (Live Map)
                      </h3>
                    </div>
                    <select
                      value={selectedMap}
                      onChange={(e) => setSelectedMap(e.target.value as "yangiyol" | "toshkent")}
                      className="bg-slate-950 text-xs font-mono font-bold text-slate-300 px-3 py-1.5 rounded-md border border-slate-800 focus:outline-none focus:border-indigo-500 cursor-pointer"
                    >
                      <option value="yangiyol">Yangiyo'l Shahri Xaritasi</option>
                      <option value="toshkent">Toshkent Shahri Xaritasi</option>
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
                        const isRouteActive = data.transportOrders.some(
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
                        const hasActiveVehicle = data.transportOrders.some(
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
                      {data.transportOrders.map((order) => {
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
                                {order.speed > 0 ? `${order.speed} km/s | ${order.progress}%` : `${order.status} (${order.progress}%)`}
                              </text>
                            </g>
                            <title>{`${order.vehicle} (${order.driverName})\nHolat: ${order.status}\nTezlik: ${order.speed} km/s\nProgress: ${order.progress}%\nYuk: ${order.material}`}</title>
                          </g>
                        );
                      })}
                    </svg>
                  </div>
                </div>

                {/* Table 2: Mechanic and Fleet Repair Logs */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <div className="w-2.5 h-2.5 rounded-full bg-red-400 animate-pulse" />
                      <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
                        Махсус Техникалар ва Ёқилғи Тарқатиш
                      </h3>
                    </div>
                    <span className="text-xs font-mono font-bold text-slate-300 bg-slate-950 px-3 py-1 rounded-md border border-slate-800">
                      ТЕХНИК АУДИТ
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 font-mono font-bold text-xs uppercase tracking-wider">
                          <th className="py-3 px-1">Код</th>
                          <th className="py-3 px-2">Транспорт Русуми</th>
                          <th className="py-3 px-2">Аниқланган Носозликлар</th>
                          <th className="py-3 px-2 text-center">Ҳолат</th>
                          <th className="py-3 px-2 text-right">Ёқилғи</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40">
                        {data.mechanicStatus.map((rep, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/40 transition duration-150">
                            <td className="py-4 px-1 font-mono text-slate-300 font-bold text-sm">{rep.id}</td>
                            <td className="py-4 px-2 font-extrabold text-slate-100 text-sm">{rep.vehicle}</td>
                            <td className="py-4 px-2 text-slate-300 font-sans text-sm max-w-[200px] truncate" title={rep.issue}>
                              {rep.issue}
                            </td>
                            <td className="py-4 px-2 text-center">
                              <span className={`px-2.5 py-1 rounded-md text-xs font-black tracking-wider ${
                                rep.status === "Соз" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                                rep.status === "Таъмирланмоқда" ? "bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse" : 
                                "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                              }`}>
                                {rep.status.toUpperCase()}
                              </span>
                            </td>
                            <td className="py-4 px-2 text-right font-mono font-black text-sm text-slate-100">
                              {rep.fuelDistributed > 0 ? (
                                <span className="text-emerald-400 bg-emerald-500/5 px-2 py-1 rounded border border-emerald-500/10">
                                  {rep.fuelDistributed} L
                                </span>
                              ) : (
                                <span className="text-slate-500">0 L</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : (
              <div className="space-y-8">
                {/* Fingerprint device panel */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* Card 1: Device status */}
                  <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden group">
                    <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <Fingerprint className="w-32 h-32 text-indigo-400" />
                    </div>
                    <div className="flex items-center space-x-4 mb-4">
                      <div className="p-3 bg-indigo-500/10 rounded-xl border border-indigo-500/20 text-indigo-400">
                        <Fingerprint className="w-6 h-6 animate-pulse" />
                      </div>
                      <div>
                        <h4 className="font-extrabold text-white text-base">ZKTeco F22 Biometrik terminal</h4>
                        <p className="text-xs text-slate-400 font-mono">ID: ZK-F22-MAIN | IP: 192.168.1.150:4370</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm font-mono font-medium">
                      <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                        <span className="text-slate-400">Ulanish holati:</span>
                        <span className="text-emerald-400 font-bold">FAOL (ONLAYN) 🟢</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                        <span className="text-slate-400">Sinxronizatsiya:</span>
                        <span className="text-indigo-400">Real-vaqt (Push API)</span>
                      </div>
                      <div className="flex justify-between pb-0.5">
                        <span className="text-slate-400">Barmoq izlari:</span>
                        <span className="text-slate-200">45 ta ro'yxatda</span>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: Attendance Stats */}
                  <div className="bg-gradient-to-br from-slate-900/80 to-slate-950/80 border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden group">
                    <div className="absolute right-0 bottom-0 translate-x-4 translate-y-4 opacity-5 group-hover:opacity-10 transition-opacity">
                      <User className="w-32 h-32 text-indigo-400" />
                    </div>
                    <div className="flex items-center space-x-4 mb-4">
                      <div className="p-3 bg-emerald-500/10 rounded-xl border border-emerald-500/20 text-emerald-400">
                        <User className="w-6 h-6" />
                      </div>
                      <div>
                        <h4 className="font-extrabold text-white text-base">Bugungi Davomat Statistikasi</h4>
                        <p className="text-xs text-slate-400 font-mono">Kunlik faol xodimlar monitori</p>
                      </div>
                    </div>
                    <div className="space-y-2 text-sm font-mono font-medium">
                      <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                        <span className="text-slate-400">Faol (Ish joyida):</span>
                        <span className="text-emerald-400 font-bold">{(data.stats.activeEmployeesCount || 0)} ta xodim</span>
                      </div>
                      <div className="flex justify-between border-b border-slate-800/60 pb-1.5">
                        <span className="text-slate-400">Oxirgi faollik:</span>
                        <span className="text-slate-200">{(data.attendanceLogs?.[0]?.timeFormatted || "--:--")} ({data.attendanceLogs?.[0]?.employeeName?.split(" ")[0] || "yo'q"})</span>
                      </div>
                      <div className="flex justify-between pb-0.5">
                        <span className="text-slate-400">Bugungi kirishlar:</span>
                        <span className="text-indigo-400">{(data.attendanceLogs?.filter(a => a.status === "Kirish").length || 0)} ta scan</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Table 3: Employee Attendance Log */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Fingerprint className="w-5 h-5 text-indigo-400" />
                      <h3 className="text-base font-extrabold text-white uppercase tracking-wider font-sans">
                        Biometrik Qurilmadan Kelgan Davomat Jurnali
                      </h3>
                    </div>
                    <span className="text-xs font-mono font-bold text-slate-300 bg-slate-950 px-3 py-1 rounded-md border border-slate-800">
                      BUGUNGI SCANLAR
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 font-mono font-bold text-xs uppercase tracking-wider">
                          <th className="py-3 px-1">Scan ID</th>
                          <th className="py-3 px-2">Xodim Ismi / Roli</th>
                          <th className="py-3 px-2">Sana / Vaqt</th>
                          <th className="py-3 px-2 text-center">Davomat Holati</th>
                          <th className="py-3 px-2 text-right">Qurilma</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40">
                        {data.attendanceLogs && data.attendanceLogs.map((log, idx) => (
                          <tr key={idx} className="hover:bg-slate-900/40 transition duration-150">
                            <td className="py-4 px-1 font-mono font-bold text-indigo-400 text-sm">{log.id}</td>
                            <td className="py-4 px-2">
                              <p className="font-extrabold text-slate-100 text-sm flex items-center space-x-1.5">
                                <span className="text-indigo-400">👤</span>
                                <span>{log.employeeName}</span>
                              </p>
                              <p className="text-xs text-slate-400 font-mono font-medium">{log.role.toUpperCase()}</p>
                            </td>
                            <td className="py-4 px-2 font-bold text-slate-200 text-sm">
                              {log.timeFormatted} <span className="text-xs text-slate-500 font-mono">({log.timestamp.slice(0, 10)})</span>
                            </td>
                            <td className="py-4 px-2 text-center">
                              <span className={`px-2.5 py-1 rounded-md text-xs font-black tracking-wider ${
                                log.status === "Kirish" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                                log.status === "Chiqish" ? "bg-orange-500/10 text-orange-400 border border-orange-500/20" : 
                                "bg-red-500/10 text-red-400 border border-red-500/20 animate-pulse"
                              }`}>
                                {log.status.toUpperCase()}
                              </span>
                            </td>
                            <td className="py-4 px-2 text-right font-mono font-bold text-sm text-slate-300">
                              {log.deviceName}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

          </div>

        </section>

      </main>

      {/* Footer copyright */}
      <footer className="border-t border-slate-800/80 mt-16 py-8 text-center text-slate-400 text-sm font-mono bg-slate-950/40 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p>© 2026 МО БОШҚАРУВ ПАНЕЛИ - ИНТЕЛЛЕКТУАЛ НАЗОРАТ ТИЗИМИ</p>
          <p className="text-xs text-slate-500">Симуляция ва реал вақтда маълумот узатиш тизими фаол</p>
        </div>
      </footer>

    </div>
  );
}
