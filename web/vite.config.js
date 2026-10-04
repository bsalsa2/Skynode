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
      // URLs inside the CSS are relative to its own folder (assets/); rebase
      // them so they still resolve once the CSS lives in index.html.
      const dir = file.fileName.includes('/') ? file.fileName.replace(/[^/]+$/, '') : '';
      const css = String(file.source).replace(
        /url\((['"]?)\.\/(?!\/)/g,
        (_, q) => `url(${q}./${dir}`
      );
      html.source = html.source.replace(tag, () => `<style>${css}</style>`);
      delete bundle[name];
    }
  },
});

// Preloads the two fonts the first screen needs (headline + body text).
const preloadFonts = () => ({
  name: 'skynode-preload-fonts',
  apply: 'build',
  transformIndexHtml: {
    order: 'post',
    handler(html, ctx) {
      const wanted = ['jura-latin-300-normal', 'dm-sans-latin-400-normal'];
      const files = Object.keys(ctx.bundle || {}).filter(
        (f) => f.endsWith('.woff2') && wanted.some((w) => f.includes(w))
      );
      return files.map((f) => ({
        tag: 'link',
        attrs: { rel: 'preload', href: `./${f}`, as: 'font', type: 'font/woff2', crossorigin: '' },
        injectTo: 'head',
      }));
    },
  },
});

// Relative base so the build works on any host, at the domain root or under
// a sub-path.
export default defineConfig({
  base: './',
  plugins: [skynodeContent(), preloadFonts(), inlineCss()],
  build: {
    outDir: 'dist',
    target: 'es2020',
    // three.js lives in its own lazy-loaded chunk; it is big by nature.
    chunkSizeWarningLimit: 700,
  },
});
