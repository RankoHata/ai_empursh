import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  root: '.',
  resolve: {
    alias: {
      '@framework': path.resolve(__dirname, 'src/live2d/framework'),
    },
  },
  build: {
    outDir: '.vite/renderer/main_window',
  },
});
