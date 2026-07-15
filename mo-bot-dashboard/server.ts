import express from "express";
import path from "path";
import dotenv from "dotenv";
import cors from "cors";
import helmet from "helmet";
import rateLimit from "express-rate-limit";
import { setupDatabase } from "./server/db.js";
import { router as apiRouter } from "./server/api.js";

dotenv.config();

const app = express();
const PORT = Number(process.env.PORT ?? 3001);

// --- Security Middleware ---
// 1. CORS - Cross-Origin Resource Sharing ruxsatlari
app.use(cors());

// 2. Helmet - Xavfsizlik bo'yicha HTTP headerlarni o'rnatish
// Vite dev server bilan ishlashi uchun contentSecurityPolicy o'chirilgan
app.use(helmet({
  contentSecurityPolicy: false,
}));

// 3. Umumiy Rate Limiting - DDoS hujumlari va botlarni cheklash
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 daqiqa
  max: 1000, // Har bir IP uchun 15 daqiqada 1000 ta so'rov
  message: "Juda ko'p so'rov yuborildi. Iltimos, birozdan so'ng qayta urinib ko'ring."
});
app.use(limiter);

app.use(express.json());

// Load API Routes
app.use("/api", apiRouter);

// Export app for serverless (Vercel)
export default app;

// Vite Dev Server / Production Static Serving
async function startServer() {
  await setupDatabase();
  
  if (process.env.NODE_ENV !== "production" && process.env.VERCEL !== "1") {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
    
    app.listen(PORT, "0.0.0.0", () => {
      console.log(`MO Bot Dashboard server is running on http://localhost:${PORT}`);
    });
  } else if (!process.env.VERCEL) {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
    app.listen(PORT, "0.0.0.0", () => {
      console.log(`MO Bot Dashboard server is running on http://localhost:${PORT}`);
    });
  }
}

if (!process.env.VERCEL) {
  startServer().catch((err) => {
    console.error("Server start error:", err);
  });
}

process.on("uncaughtException", (err) => {
  console.error("Uncaught Exception:", err);
});

process.on("unhandledRejection", (err) => {
  console.error("Unhandled Rejection:", err);
});
