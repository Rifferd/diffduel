import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      // Свой SW (injectManifest): прекэш app shell + офлайн-fallback + push-хук.
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.ts',
      registerType: 'autoUpdate',
      // Манифест уже лежит в public/manifest.webmanifest — не дублируем иконки.
      manifest: false,
      injectRegister: 'auto',
      injectManifest: {
        // offline.html и иконки попадают в прекэш через glob (app shell).
        globPatterns: ['**/*.{js,css,html,svg,png,webmanifest}'],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      '@ds': fileURLToPath(new URL('../../packages/design-system', import.meta.url)),
    },
  },
  server: {
    port: 5173,
  },
});
