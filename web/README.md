# Skynode website

The landing page for Skynode: a single static page built with Vite, vanilla
JavaScript, Three.js, and GSAP. Everything below can be done from a web
browser.

| Where | Address | How it updates |
| --- | --- | --- |
| Netlify | **https://skynode-si.netlify.app** | Every push to `main` (project `skynode-si`) |

---

## Netlify

The Netlify project **skynode-si** builds this repo on Netlify's servers.
The `netlify.toml` at the repo root tells it to build `web/` (`npm run
build`, publish `web/dist`), so nothing in the dashboard needs filling in.

- **Production** (https://skynode-si.netlify.app) is built from `main` and is
  public.
- **Pull requests** get a preview deploy (link in the PR checks). Previews
  need a Netlify login to view.
- **Rename the address:** Project configuration → General → **Change
  project name**. Then update `meta.url` in `web/src/content.js` so share
  previews use the new address.
- **Not linked to this repo yet?** Project configuration → Build & deploy
  → Continuous deployment → **Link repository** → GitHub →
  `bsalsa2/Skynode`, branch `main`. Leave the other fields empty.
- **A deploy failed?** Open **Deploys**, click the red deploy, and read the
  log. A problem in `content.js` is explained there, with the line number.

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

You'll see it in Netlify under **Deploys**: click the failed deploy and
read the log. On a pull request, the problems also show up as annotations
in the **Check site** results.

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

## Visit counter (GoatCounter)

The site can count visits with GoatCounter: free for personal sites, no
cookies, and nothing that identifies a visitor.

1. Sign up at **goatcounter.com** and pick a code, for example `skynode`.
   Your dashboard will be at `https://skynode.goatcounter.com`.
2. In `web/src/content.js`, set `analytics.goatcounter` to that code and
   commit.

The counter loads on both pages, and the privacy page automatically
switches to wording that explains the counter. To turn it off, set the code
back to `''`.

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
  src/styles.css          liquid glass and layout (brand tokens come from graphite.css)
  ../brain/dashboard/graphite.css   the shared brand tokens: colours, glass, type stacks.
                          The live dashboard loads the same file, so a colour changes in both
  src/fonts.css           self-hosted Saira, IBM Plex Sans, IBM Plex Mono
  src/main.js             scroll story, nav, buttons, glass tilt, lazy loading
  src/hero.js             hero sky: stars, the aircraft pass, live readout card
  src/sensor.js           the simulated sensor view in "How it works"
  src/mount.js            the Three.js pan-tilt mount viewer
  src/three-env.js        studio lighting for the mount viewer
.github/workflows/check-site.yml    checks content.js and the build on pull requests
```

Design: **Liquid Graphite** (the Skynode brand system). Carbon, smoke and
light; colour appears only for what the sensor sees (drone red, aircraft
blue, clear green), so a colour on screen always means something. Saira for
headings, IBM Plex Sans for text, IBM Plex Mono for data.

How it behaves:
- **Hero:** the planet's bright rim and the moon are plain CSS, so they are
  there on first paint. After load, a small canvas adds twinkling stars and,
  every so often, an aircraft crossing the sky; a blue lock box closes in on
  it and the glass card shows the pan/tilt the node would command. It's
  labelled as a concept, and pauses when scrolled away or the tab is hidden.
- **Sensor view:** a simulation of the overlay from `brain/overlay.py`. The
  camera pans to keep the locked drone in the centre ring. Labelled as
  simulated on the page; it only runs while on screen.
- **3D mount:** loads when it's about to scroll into view and pauses off
  screen. Drag it to turn it. Hover a part name to highlight that part.
- **No WebGL, software-only WebGL, or a slow device:** the mount shows a
  still image instead. Add `?gl=any` to the URL to force 3D anyway.
- **Reduced motion:** no scroll animation and no motion; the hero sky and
  the sensor view are drawn once as stills.
- **Liquid glass:** frosted blur everywhere. Chrome and Edge also get a
  refraction effect; Safari and Firefox keep the plain blur.
- **Privacy:** fonts and scripts are served from the site itself. The only
  third-party request is the optional GoatCounter visit counter.

---

## Performance

Lighthouse, mobile preset (simulated slow 4G and a 4× slower CPU), measured
against the production build before the Liquid Graphite redesign (re-run it
on the live URL to get current numbers):

| Performance | Accessibility | Best practices | SEO |
| :---------: | :-----------: | :------------: | :-: |
|   97 – 99   |      100      |      100       | 100 |

FCP 1.4–1.5 s · LCP 1.8–1.9 s · TBT 120–150 ms · CLS 0

Lighthouse runs Chrome without a GPU, so it gets the static images, not the
3D views. On a real phone, the 3D loads after the first paint, so first
paint and LCP stay the same. To measure on real hardware, run PageSpeed
Insights (pagespeed.web.dev) on the live URL.
