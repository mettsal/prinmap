import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
// The frontend talks to the FastAPI backend through a dev proxy so the browser
// only ever sees same-origin `/api` requests (no CORS surprises in dev).
export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                changeOrigin: true,
            },
        },
    },
});
