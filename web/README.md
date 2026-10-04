# Skynode website

The landing page for Skynode: a single static page built with Vite, vanilla
JavaScript, Three.js, and GSAP. Everything below can be done from a web
browser.

| Where | Address | How it updates |
| --- | --- | --- |
| Netlify | **https://skynode-tracker.netlify.app** | Every push to the branch you link (one-time setup below) |
| GitHub Pages | https://bsalsa2.github.io/Skynode/ | Every merge to `main` that touches `web/` or `hardware/*.stl` |

The Netlify project `skynode-tracker` already exists. It only needs to be
linked to this repo once.

---

## Put it on Netlify (browser, about 2 minutes, one time)

1. Go to **app.netlify.com → Projects → skynode-tracker**.
2. Open **Project configuration → Build & deploy → Continuous deployment**
   and click **Link repository**.
3. Choose **GitHub**, then **bsalsa2/Skynode**. If it isn't listed, click
   "Configure the Netlify app on GitHub" and give it access to this repo.
4. Fill in:
   - **Branch to deploy:** `main` (after this work is merged). To see it
     before merging, pick `claude/skynode-landing-page-3jsami`, then switch
     it to `main` later in the same screen.
   - **Base directory:** `web`
   - Leave the build command and publish directory empty. `web/netlify.toml`
     already says `npm run build` and `dist`.
5. Click **Deploy**. About a minute later the site is live at
   https://skynode-tracker.netlify.app. After that, every push to that
   branch redeploys it.

To rename the address, go to **Project configuration → General → Project
details → Change project name**. Then update `meta.url` in
`web/src/content.js` so share previews use the new address.

## Put it on GitHub Pages (browser, one time)

1. On github.com, open the repo and go to **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
3. Merge into `main`. The **Deploy site to GitHub Pages** run in the
   **Actions** tab takes about a minute; its `deploy` box shows the link.

## Vercel instead (optional)

At **vercel.com/new**, import **bsalsa2/Skynode**, set **Root Directory** to
`web`, and keep the detected Vite settings. Vercel also redeploys on every
push.

---

## Update the text (including the Status list)

All the words on the page live in one file:
**[`web/src/content.js`](src/content.js)**.

1. Open `web/src/content.js` on github.com and click the pencil icon.
2. Change the text between the quotes. For a status item, set its label to
   exactly `'DONE'`, `'IN PROGRESS'`, or `'NEXT'`. The colour and icon
   follow automatically.
3. To add a status item, copy a whole line like
   `{ label: 'NEXT', text: '...' },` and edit it.
4. Click **Commit changes**. The site rebuilds itself in about a minute.

**Every build checks this file first.** If something's off, nothing gets
published, and the check says what to fix and on which line. For example:

```
ERROR  web/src/content.js:103
       Typo: Unexpected identifier 's'. Usual causes: a missing comma at the
       end of the line above, a missing quote, or an apostrophe inside
       'single quotes' (wrap that text in backticks instead).
```

You'll see it in the red step of the Actions run (or the Netlify deploy
log). On a pull request, the problems also show up as annotations in the
**Check site** results.
The check catches typos, empty fields, wrong status labels, links to
sections that don't exist, video files that weren't uploaded, results with
no source, and leftover placeholder text.

Tips:
- Keep the commas at the end of each `{ ... },` line.
- If your text has an apostrophe (like `I'm`), wrap it in backticks
  `` `like this` `` instead of single quotes.

## When there's real footage

1. Upload a short clip to `web/public/media/` (on github.com: open the
   folder, then **Add file → Upload files**). MP4 works everywhere; keep it
   under about 10 MB.
2. In `content.js`, under `hero.footage`, set `video` to its path (for
   example `'media/first-track.mp4'`) and write a `caption` that says what it
   shows. A `poster` image is optional.
3. Commit. The clip replaces the concept visualization at the top of the
   page. It plays muted on a loop, and stays paused with controls for
   visitors who have turned off motion.

Before you publish a clip, check that it doesn't show your house, your
street, or anything else that reveals where you live.

## When there are accuracy numbers

In `content.js`, add entries to `results.items`, for example
`{ value: '91%', label: 'Aircraft detected', note: 'Daytime, clear sky' }`,
and fill in `results.source` with how and when they were measured. A
**Results** section appears after Status. It stays hidden while `items` is
empty, and the build refuses numbers without a source.

## The 3D pan-tilt mount

The mount in "How it works" is your real CAD design. Before each build,
`web/scripts/build-models.mjs` packs `hardware/pantilt_*.stl` into one small
file (`web/public/models/pantilt.bin`, about 108 KB instead of 615 KB). The
page places the parts exactly as `assembly()` in `hardware/pantilt.py` does.
So when you change the CAD and re-export the STLs, the website updates on
the next deploy.

If you move the assembly offsets in `pantilt.py` (for example
`horn_seat_z`), copy the same numbers to the top of `web/src/mount.js`.

The still image shown before the 3D loads is
`web/public/models/pantilt-still.webp`.

## The Sunnode card

The card above the footer links to Sunnode. To add a one-sentence
description, fill in `sister.description` in `content.js`.

---

## What's in here

```
web/
  index.html              page shell
  vite.config.js          build: content.js -> static HTML, inline CSS, font preloads
  netlify.toml            Netlify build settings and caching
  public/                 favicon, share image, robots.txt, models/
  scripts/check-content.mjs   validates content.js (runs before every build)
  scripts/build-models.mjs    packs hardware/*.stl for the 3D mount viewer
  src/content.js          ALL page copy and status items  <- edit this
  src/render.js           HTML templates for each section
  src/styles.css          design tokens, liquid glass, layout
  src/fonts.css           self-hosted Jura, DM Sans, DM Mono
  src/main.js             scroll animation, nav, buttons, card tilt, lazy loading
  src/scene.js            the Three.js hero
  src/mount.js            the Three.js pan-tilt mount viewer
  src/three-env.js        shared studio lighting for both 3D views
.github/workflows/deploy-site.yml   builds web/ and publishes to GitHub Pages
.github/workflows/check-site.yml    checks content.js and the build on pull requests
```

How it behaves:
- **3D hero:** a glass sensor orb, an aircraft circling it, and an amber
  reticle that tracks the aircraft. It's generated in code. Three.js loads
  only after the page has painted. Rendering pauses when the tab is hidden
  or the scene has scrolled away, and pixel density is capped at 2.
- **3D mount:** loads when it's about to scroll into view and pauses off
  screen. Drag it to turn it. Hover a part name to highlight that part.
- **No WebGL, software-only WebGL, or a slow device:** static images are
  shown instead (an SVG hero and a still of the mount). Add `?gl=any` to the
  URL to force 3D anyway, for testing.
- **Reduced motion:** no scroll animation, no pinning, and no motion. Both
  3D views are drawn once as stills.
- **Liquid glass:** frosted blur everywhere. Chrome and Edge also get a
  refraction effect on key cards; Safari and Firefox keep the plain blur.
- **Privacy:** fonts are served from the site itself. There are no
  third-party requests at all: no analytics, no trackers, and no cookies.

---

## Performance

Lighthouse, mobile preset (simulated slow 4G and a 4× slower CPU), measured
against the production build:

| Performance | Accessibility | Best practices | SEO |
| :---------: | :-----------: | :------------: | :-: |
|   97 – 99   |      100      |      100       | 100 |

FCP 1.4–1.5 s · LCP 1.8–1.9 s · TBT 120–150 ms · CLS 0

Lighthouse runs Chrome without a GPU, so it gets the static images, not the
3D views. On a real phone, the 3D loads after the first paint, so first
paint and LCP stay the same. To measure on real hardware, run PageSpeed
Insights (pagespeed.web.dev) on the live URL.
