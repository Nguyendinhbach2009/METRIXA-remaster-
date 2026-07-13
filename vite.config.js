import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
    plugins: [react(), tailwindcss()],
    base: "/paper-project-redo/",
    server: {
        allowedHosts: [".ngrok-free.dev", "sixty-planets-enter.loca.lt"],
        host: "0.0.0.0",
        port: 5173,
    },
    preview: {
        host: "0.0.0.0",
        port: 5173,
    },
});
