import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Bu proje daha önce hiçbir test framework'üne sahip değildi (Milestone 21 —
// Web AI Trip Optimizer — kadar) — Next.js App Router + React 19 için en
// yaygın, resmi olarak desteklenen çift (Vitest + Testing Library) burada
// eklendi, spesifikasyonun kendi "Add tests following the existing web test
// framework" gereksinimini karşılamak için minimum gerekli araç.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
