import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Builds into node-api/public/command so the existing Express server serves
// the dashboard at /command/ under the same strict CSP (all assets self-hosted).
export default defineConfig({
  base: '/command/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../node-api/public/command',
    emptyOutDir: true
  },
  server: {
    proxy: {
      '/api': 'http://localhost:3000'
    }
  }
});
