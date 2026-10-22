/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_');
  const apiTarget = env.VITE_DEV_API_PROXY_TARGET ?? 'http://localhost:8000';
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      proxy: {
        // `ws: true` proxies the realtime WebSocket upgrade (DEC-022).
        '/api': { target: apiTarget, changeOrigin: true, ws: true },
      },
    },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
      restoreMocks: true,
      // Multi-step MUI dialog integration tests are slow on 2-core CI runners (first CI timeout at 5 s).
      testTimeout: 20_000,
    },
  };
});
