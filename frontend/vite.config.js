import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// В разработке запросы /api проксируются на Flask (python app.py, порт 5000)
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:5000" } },
});
