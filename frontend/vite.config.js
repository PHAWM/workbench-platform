import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      src: path.resolve(__dirname, './src'), // This fixes the "src" import error you had
    },
  },
  server: {
    port: 3000,
    open: true,
  },
});