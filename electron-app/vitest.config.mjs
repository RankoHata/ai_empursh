import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  root: '.',
  assetsInclude: ['**/*.skel', '**/*.atlas'],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/renderer/test-setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
  },
});
