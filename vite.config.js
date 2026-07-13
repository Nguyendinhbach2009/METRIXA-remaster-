import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { viteStaticCopy } from "vite-plugin-static-copy";

// https://vite.dev/config/
export default defineConfig({
    plugins: [
        react(), 
        tailwindcss(),
        viteStaticCopy({
            targets: [
                {
                    src: "src/data/*.json",
                    dest: "data"
                },
                {
                    src: "src/data/rankings/**/*",
                    dest: "data/rankings"
                }
            ]
        })
    ],
    base: "/",
    build: {
        rollupOptions: {
            input: {
                main: "index.html",
                ranking: "ranking.html"
            }
        }
    },
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
