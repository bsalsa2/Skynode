import { defineConfig } from 'vite';
import { content } from './src/content.js';
import { renderHead, renderBody } from './src/render.js';

// Renders src/content.js into index.html at build time, so the page is
// plain static HTML (fast, readable without JavaScript, good for search).
const skynodeContent = () => ({
  name: 'skynode-content',
  transformIndexHtml(html) {
    return html
      .replace('<!--skynode:head-->', renderHead(content))
      .replace('<!--skynode:body-->', renderBody(content));
  },
});

// Relative base so the build works at https://bsalsa2.github.io/Skynode/
// regardless of how the repo name is capitalised, and on Netlify/Vercel too.
export default defineConfig({
  base: './',
  plugins: [skynodeContent()],
  build: {
    outDir: 'dist',
    target: 'es2020',
    // three.js lives in its own lazy-loaded chunk; it is big by nature.
    chunkSizeWarningLimit: 700,
  },
});
