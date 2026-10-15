import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  // GitHub Pages serverar projektsidor under /<repo>/. Bygget får rätt bas via VITE_BASE.
  base: process.env.VITE_BASE ?? "/",
  plugins: [react()],
  // MapLibre 6 startar en ESM-worker via sin egen filsökväg (import.meta.url). Förbundlas biblioteket i devläge bryts den
  // sökvägen ("Worker failed to load"), så det laddas direkt ur node_modules istället.
  optimizeDeps: { exclude: ["maplibre-gl"] },
  build: { chunkSizeWarningLimit: 1200 }, // MapLibre är stort och laddas ändå bara en gång
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
    css: false,
  },
});
