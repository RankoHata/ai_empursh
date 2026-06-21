import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  resolve: {
    alias: {},
  },
  assetsInclude: ['**/*.skel', '**/*.atlas'],
  build: {
    outDir: '.vite/renderer/main_window',
  },
});
