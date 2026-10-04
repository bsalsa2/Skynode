import { defineConfig } from 'vite';

// Relative base so the build works at https://bsalsa2.github.io/Skynode/
// regardless of how the repo name is capitalised, and on Netlify/Vercel too.
export default defineConfig({
  base: './',
  build: {
    outDir: 'dist',
    target: 'es2020',
    assetsInlineLimit: 0,
  },
});
