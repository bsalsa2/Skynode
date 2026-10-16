import { defineConfig } from 'vite';
import { content } from './src/content.js';
import { fileURLToPath } from 'node:url';
import {
  renderHead,
  renderBody,
  renderPrivacyHead,
  renderPrivacyBody,
  renderContactHead,
  renderContactBody,
} from './src/render.js';

// Renders src/content.js into index.html at build time, so the page is
// plain static HTML (fast, readable without JavaScript, good for search).
const taloContent = () => ({
  name: 'talo-content',
  transformIndexHtml(html) {
    return html
      .replace('<!--talo:head-->', renderHead(content))
      .replace('<!--talo:body-->', renderBody(content))
      .replace('<!--talo:privacy-head-->', renderPrivacyHead(content))
      .replace('<!--talo:privacy-body-->', renderPrivacyBody(content))
      .replace('<!--talo:contact-head-->', renderContactHead(content))
      .replace('<!--talo:contact-body-->', renderContactBody(content));
  },
});

// Inlines the (small) stylesheet into index.html so the first paint doesn't
// wait on a second request.
const inlineCss = () => ({
  name: 'talo-inline-css',
  apply: 'build',
  enforce: 'post',
  generateBundle(_, bundle) {
    const pages = Object.values(bundle).filter((f) => f.fileName.endsWith('.html'));
    for (const [name, file] of Object.entries(bundle)) {
      if (!name.endsWith('.css')) continue;
      const tag = new RegExp(`<link[^>]*href="[^"]*${file.fileName.split('/').pop()}"[^>]*>`);
      const users = pages.filter((p) => tag.test(p.source));
      if (!users.length) continue;
      // URLs inside the CSS are relative to its own folder (assets/); rebase
      // them so they still resolve once the CSS lives in index.html.
      const dir = file.fileName.includes('/') ? file.fileName.replace(/[^/]+$/, '') : '';
      const css = String(file.source).replace(
        /url\((['"]?)\.\/(?!\/)/g,
        (_, q) => `url(${q}./${dir}`
      );
      for (const page of users) page.source = page.source.replace(tag, () => `<style>${css}</style>`);
      delete bundle[name];
    }
  },
});

// Preloads the two fonts the first screen needs (headline + body text).
const preloadFonts = () => ({
  name: 'talo-preload-fonts',
  apply: 'build',
  transformIndexHtml: {
    order: 'post',
    handler(html, ctx) {
      const wanted = ['saira-latin-300-normal', 'ibm-plex-sans-latin-400-normal'];
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
  // graphite.css (shared brand tokens) lives in ../brain/dashboard
  server: { fs: { allow: ['..'] } },
  plugins: [taloContent(), preloadFonts(), inlineCss()],
  build: {
    outDir: 'dist',
    target: 'es2020',
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        privacy: fileURLToPath(new URL('./privacy.html', import.meta.url)),
        contact: fileURLToPath(new URL('./contact.html', import.meta.url)),
        field: fileURLToPath(new URL('./field.html', import.meta.url)),
      },
    },
    // three.js lives in its own lazy-loaded chunk; it is big by nature.
    chunkSizeWarningLimit: 700,
  },
});
