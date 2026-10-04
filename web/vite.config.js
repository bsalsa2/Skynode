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

// Inlines the (small) stylesheet into index.html so the first paint doesn't
// wait on a second request.
const inlineCss = () => ({
  name: 'skynode-inline-css',
  apply: 'build',
  enforce: 'post',
  generateBundle(_, bundle) {
    const html = Object.values(bundle).find((f) => f.fileName === 'index.html');
    if (!html) return;
    for (const [name, file] of Object.entries(bundle)) {
      if (!name.endsWith('.css')) continue;
      const tag = new RegExp(`<link[^>]*href="[^"]*${file.fileName.split('/').pop()}"[^>]*>`);
      if (!tag.test(html.source)) continue;
      html.source = html.source.replace(tag, () => `<style>${file.source}</style>`);
      delete bundle[name];
    }
  },
});

// Relative base so the build works at https://bsalsa2.github.io/Skynode/
// regardless of how the repo name is capitalised, and on Netlify/Vercel too.
export default defineConfig({
  base: './',
  plugins: [skynodeContent(), inlineCss()],
  build: {
    outDir: 'dist',
    target: 'es2020',
    // three.js lives in its own lazy-loaded chunk; it is big by nature.
    chunkSizeWarningLimit: 700,
  },
});
