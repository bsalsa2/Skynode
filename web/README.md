# Skynode website

The landing page for Skynode: a single static page built with Vite, vanilla
JavaScript, Three.js, and GSAP. It deploys for free on GitHub Pages and
everything here can be done from a web browser.

Live URL (after the first deploy): **https://bsalsa2.github.io/Skynode/**

---

## Publish it (browser only, one time)

1. On github.com, open the repo and go to **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
   (There is nothing else to fill in.)
3. Merge the pull request into `main`.
4. Open the **Actions** tab. The run called **Deploy site to GitHub Pages**
   takes about a minute. When it shows a green check, click it: the
   `deploy` box has the live link.

After that, every change merged into `main` that touches `web/` republishes
the site automatically. To republish by hand, go to **Actions → Deploy site
to GitHub Pages → Run workflow**.

If a run fails, click it and open the red step to read the error. The most
common cause is that step 2 was skipped.

---

## Update the text (including the Status list)

All the words on the page live in one file:
**[`web/src/content.js`](src/content.js)**.

1. Open `web/src/content.js` on github.com and click the pencil icon.
2. Change the text between the quotes. For a status item, change its label
   to exactly `'DONE'`, `'IN PROGRESS'`, or `'NEXT'`. The colour and icon
   follow automatically.
3. To add a status item, copy a whole line like
   `{ label: 'NEXT', text: '...' },` and edit it.
4. Click **Commit changes**. Commit straight to `main` (or open a pull
   request and merge it). The site rebuilds itself in about a minute.

Tips:
- Keep the commas at the end of each `{ ... },` line.
- If your text has an apostrophe (like `I'm`), wrap it in backticks
  `` `like this` `` instead of single quotes. The file already does this
  where needed.
- If the Actions run turns red after an edit, the error usually points at a
  missing quote or comma in `content.js`.

---

## What's in here

```
web/
  index.html          page shell (meta tags, fonts)
  vite.config.js      build settings; turns content.js into static HTML
  public/             favicon, social share image, robots.txt
  src/content.js      ALL page copy and status items  <- edit this
  src/render.js       HTML templates for each section
  src/styles.css      design tokens, liquid glass, layout
  src/main.js         scroll animation, nav, buttons, card tilt
  src/scene.js        the Three.js hero (lazy-loaded)
.github/workflows/deploy-site.yml   builds web/ and publishes to Pages
```

How it behaves:
- **3D hero.** A glass sensor orb, an aircraft circling it, and an amber
  reticle that tracks the aircraft. It's all generated in code, with no
  downloaded models or images. Three.js only loads after the page has
  painted. Rendering pauses when the tab is hidden or the scene has scrolled
  away. Pixel density is capped at 2 and drops automatically on slow
  devices.
- **No WebGL, or software-only WebGL.** A static SVG version of the hero is
  shown instead. The same happens if a device can't keep a smooth frame
  rate.
- **Reduced motion.** If the visitor's system has "reduce motion" turned on,
  there are no scroll animations, no pinning, and no motion. The 3D scene
  is drawn once as a still image.
- **Liquid glass.** Frosted blur everywhere. Chromium browsers (Chrome,
  Edge, Arc) also get a refraction effect on key cards. Safari and Firefox
  keep the clean blur.
- **Privacy.** There's no analytics, no trackers, and no cookies. The only
  third-party request is Google Fonts.

---

## Performance

Lighthouse, mobile preset (simulated slow 4G and a 4× slower CPU), measured
against the production build:

| Performance | Accessibility | Best practices | SEO |
| :---------: | :-----------: | :------------: | :-: |
|   96 – 99   |      100      |      100       | 100 |

FCP 1.1 s · LCP 1.1 s · TBT 120–220 ms · CLS 0.014

Caveat: Lighthouse runs Chrome without a GPU. It falls into the
software-WebGL rule above, so these numbers measure the page with the
static hero. On a real phone with a GPU, the 3D scene loads after the first
paint, so first paint and LCP don't change, but the device does extra GPU
work afterwards. To check on real hardware, run PageSpeed Insights
(pagespeed.web.dev) on the live URL, or use Chrome DevTools → Lighthouse on
your own phone.

---

## Other hosts

The build is a plain static folder (`web/dist`) with relative paths, so it
also works on Netlify or Vercel. Import the repo, set the base directory to
`web`, the build command to `npm run build`, and the output directory to
`dist`.
