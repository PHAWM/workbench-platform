import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  // loadEnv reads .env files so VITE_TENANT_ID is available at config time
  const env = loadEnv(mode, process.cwd(), '');
  const tenantId = env.VITE_TENANT_ID || '';

  // Each tenant deployment gets its own base path: /workbench/<tenantId>/
  // Superuser / local dev (no tenant) uses the root.
  const base = tenantId ? `/workbench/${tenantId}/` : '/';

  // Cache-busting token appended to every asset filename. Bump VITE_BUILD_VERSION
  // (or rely on the timestamp fallback) so each deploy emits filenames Cloudflare
  // has never cached, sidestepping stale-asset MIME errors behind the CDN.
  const buildVersion = env.VITE_BUILD_VERSION || `b${Date.now()}`;

  return {
    plugins: [react()],
    base,
    resolve: {
      alias: {
        src: path.resolve(__dirname, './src'),
      },
    },
    build: {
      rollupOptions: {
        output: {
          entryFileNames: `assets/[name]-[hash]-${buildVersion}.js`,
          chunkFileNames: `assets/[name]-[hash]-${buildVersion}.js`,
          assetFileNames: `assets/[name]-[hash]-${buildVersion}[extname]`,
        },
      },
    },
    server: {
      port: 3000,
      open: true,
      allowedHosts: ['phawm.ngrok.app'],
    },
  };
});
