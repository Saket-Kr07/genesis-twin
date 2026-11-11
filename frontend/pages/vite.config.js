import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Port 5173 is the origin the backend allows (CORS).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true, host: true },
});