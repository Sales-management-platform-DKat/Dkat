import {defineConfig} from 'vite';

const apiProxy = {
  '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
};

export default defineConfig({
  server: {
    allowedHosts: ['terminal.local', '.trycloudflare.com'],
    proxy: apiProxy,
  },
  preview: { allowedHosts: ['terminal.local', '.trycloudflare.com'] },
  base: './',
});
