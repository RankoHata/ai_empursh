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
  assetsInclude: ['**/*.moc3', '**/*.model3.json', '**/*.motion3.json'],
  build: {
    outDir: '.vite/renderer/main_window',
  },
});
