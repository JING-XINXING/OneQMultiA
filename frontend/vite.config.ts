import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const API_PORT = process.env.ONEQMULTIA_API_PORT || "38421";
const VITE_PORT = Number(process.env.ONEQMULTIA_VITE_PORT || 38423);

export default defineConfig({
  plugins: [react()],
  server: {
    // host: true → 监听所有网卡（含 IPv4 127.0.0.1 与局域网 IP），
    // 修复只绑定 IPv6 [::1] 导致 127.0.0.1 无法访问的问题，同时便于手机端局域网访问
    host: true,
    port: VITE_PORT,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${API_PORT}`,
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
