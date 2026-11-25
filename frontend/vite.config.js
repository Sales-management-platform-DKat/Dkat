import {defineConfig} from 'vite';

const apiProxy = {
  '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  '/health': { target: 'http://127.0.0.1:8000', changeOrigin: true },
};

export default defineConfig({
  // Use the classic JSX factory so the existing centralized React.createElement
  // localization hook also receives literal JSX text in the legacy screens.
  esbuild: {
    jsx: 'transform',
    jsxFactory: 'React.createElement',
    jsxFragment: 'React.Fragment',
  },
  server: {
    allowedHosts: ['terminal.local', '.trycloudflare.com'],
    proxy: apiProxy,
  },
  preview: { allowedHosts: ['terminal.local', '.trycloudflare.com'] },
  base: './',
});
