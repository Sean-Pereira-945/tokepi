import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const API_TARGET = 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../driftguard/server/static',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Keep the charting library out of the app chunk so app changes stay cache-friendly.
        manualChunks: {
          charts: ['recharts'],
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/auth': API_TARGET,
      '/projects': API_TARGET,
      '/events': API_TARGET,
      '/agent-events': API_TARGET,
      '/health': API_TARGET,
      '/ws': { target: API_TARGET, ws: true },
    },
  },
});
