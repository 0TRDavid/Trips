import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    // Le navigateur appelle /api sur le port 5173 ; Vite relaie vers le
    // conteneur backend. Pas de CORS, pas d'URL d'API codée en dur.
    proxy: {
      "/api": "http://backend:8000",
    },
  },
});
