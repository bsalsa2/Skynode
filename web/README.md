# Varn website

The landing page for Varn: a single static page built with Vite and a few
kilobytes of vanilla JavaScript, to the approved design in
[`docs/design/home-mockup.webp`](../docs/design/home-mockup.webp).
Everything below can be done from a web browser.

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

## GitHub Pages (second host, free)

`.github/workflows/pages.yml` builds `web/` and publishes it to GitHub Pages
on every push to `main`: **https://bsalsa2.github.io/varn/**. Netlify keeps
working as before; nothing here changes its settings.

One-time setup: in the repo, **Settings → Pages → Build and deployment →
Source: GitHub Actions**. After that, the next push to `main` (or
**Actions → Deploy to GitHub Pages → Run workflow**) deploys.

How it works at a sub-path: `vite.config.js` uses a relative base (`./`), so
CSS, fonts, images and the 3D model load from wherever the page lives, at the
domain root on Netlify or under `/varn/` on Pages. Links inside the pages are
relative too. The workflow sets `SITE_URL` so the canonical and share-image
addresses point at the Pages URL; builds without it (Netlify) keep
`meta.url` from `content.js`.

---

## Vercel instead (optional)

At **vercel.com/new**, import **bsalsa2/Skynode**, set **Root Directory** to
`web`, and keep the detected Vite settings. Vercel also redeploys on every
push.

---

## Update the text

All the words on the page live in one file:
**[`web/src/content.js`](src/content.js)**, in page order: `hero`,
`project` (how it works and the sample dashboard), `results`, `roadmap`,
`footer`.

1. Open `web/src/content.js` on github.com and click the pencil icon.
2. Change the text between the quotes.
3. Click **Commit changes**. The site rebuilds itself in about a minute.

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

The check catches typos, empty fields, links to sections that don't exist,
leftover placeholder text, and the honesty rules: a result card whose number
isn't in `results.source`, a simulated panel or drone without the word
SAMPLE, a roadmap date that is already in the past, a status row that stops
saying "prototype", and a copyright line that reads like a registered
company.

Tips:
- Keep the commas at the end of each `{ ... },` line.
- If your text has an apostrophe (like `I'm`), wrap it in backticks
  `` `like this` `` instead of single quotes.

## When there are new results

In `content.js`, edit `results.cards` (icon, title, value, two caption
lines) and put how and when each number was measured in `results.source`.
The build refuses a percentage that `results.source` doesn't mention.

## When the roadmap has dates

`roadmap.steps[].when` says `Next`, `Then`, ... Replace them with real
quarters (for example `Q1 2027`) once you have them; the check flags any
date that is already in the past.

## Photos

The hero sky, the roadmap peak and the dashboard's camera view are cut from
the design itself by `brand/src/extract_mockup.py` (it paints out the text
and UI baked into the image). To use your own photos instead, replace
`web/src/assets/hero-sky.webp` (keep the drone and the 1024 x 462 framing,
or move the tracking overlay in `render.js`), `roadmap-peak.webp` and
`feed-sky.webp`.

## Visit counter (GoatCounter)

The site can count visits with GoatCounter: free for personal sites, no
cookies, and nothing that identifies a visitor.

1. Sign up at **goatcounter.com** and pick a code, for example `varn`.
   Your dashboard will be at `https://varn.goatcounter.com`.
2. In `web/src/content.js`, set `analytics.goatcounter` to that code and
   commit.

The counter loads on both pages, and the privacy page automatically
switches to wording that explains the counter. To turn it off, set the code
back to `''`.

## Phone upload page

`field.html` lets you record or pick a video on your phone and send it to your own Google Drive, from any browser. Nothing is installed, and the clips never pass through Varn's servers. They land in **My Drive ▸ skynode_phone_uploads**, and `training/auto_train.py` reads that folder next time it runs. (The page is hidden from search engines, but it is not secret: anyone can open it. Only people you list as test users can sign in and use it, and they upload to their own Drive, not yours.)

It asks Google for the narrow `drive.file` permission, which only covers files the page creates itself. That is why it has its own folder: it can't see or touch the rest of your Drive.

**One-time setup, about 5 minutes, in a browser (nothing on your computer):**

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project named `skynode` (top bar ▸ project picker ▸ New project).
2. **APIs & Services ▸ Library**, search **Google Drive API**, click **Enable**.
3. **APIs & Services ▸ OAuth consent screen** (called **Google Auth Platform** in newer consoles). Choose **External**. App name `Varn`, your email for support and developer contact. On the scopes step add `.../auth/drive.file` (the non-sensitive one). Leave publishing status on **Testing**. Under **Test users**, add your own Google address. Only addresses on that list can sign in.
4. **APIs & Services ▸ Credentials ▸ Create credentials ▸ OAuth client ID**. Type **Web application**. Under **Authorised JavaScript origins** add your site address exactly (for example `https://skynode-si.netlify.app`) and, to try it before publishing, the Netlify preview address. Leave redirect URIs empty. Click Create.
5. Copy the **Client ID** (it ends in `.apps.googleusercontent.com`) into `web/src/field-config.js`. **Do not copy the client secret anywhere.** The page doesn't use one.
6. Commit that one-line change, let Netlify deploy, and open `/field.html` on your phone.

Good to know while the app is in Testing: Google may show an "unverified app" warning (tap Advanced ▸ continue, it's your own app), and your sign-in lasts about an hour, so a long upload may ask you to sign in again. Both are normal. Don't click "Publish app" unless you want strangers to be able to sign in.

Check it with `npm test` (the upload logic, against a fake Drive).

## The Sunnode card

The card above the footer links to Sunnode. To add a one-sentence
description, fill in `sister.description` in `content.js`.

---

## What's in here

```
web/
  index.html              page shell
  vite.config.js          build: content.js -> static HTML, inline CSS, font preload
  netlify.toml            Netlify build settings and caching
  public/                 favicon, share image, robots.txt
  scripts/check-content.mjs   validates content.js (runs before every build)
  src/content.js          ALL page copy  <- edit this
  src/render.js           HTML for each section, icons, the hero tracking overlay
  src/home.css            layout and type, in the design's own pixels (see the top of the file)
  src/assets/             hero, roadmap and dashboard photos
  ../brain/dashboard/graphite.css   the shared brand tokens: colours and type stacks.
                          The live dashboard loads the same file, so a colour changes in both
  src/fonts.css           self-hosted Inter, Space Grotesk, Geist Mono
  src/logo.js             the mark and wordmark paths (generated by brand/src/build_brand.py)
  src/main.js             scroll reveals, hero pause, loads the dashboard simulation
  src/feed.js             the SAMPLE dashboard: moving detection boxes and the radar sweep
.github/workflows/check-site.yml    checks content.js and the build on pull requests
```

Design: the approved homepage mockup, in the **Varn brand system**
([`brand/`](../brand/)): charcoal and bone, a steel-blue accent on "sky.",
the outlined mark and wordmark. Headings and text are set in Inter, as in the
design. Sizes in `home.css` are written in mockup pixels
(`calc(N * var(--u))`), so the page keeps the design's proportions at any
width; phones get a stacked layout.

How it behaves:
- **Hero:** the tracking line draws across the sky, its dots appear, and the
  frame locks onto the drone, then pulses slowly. The drone is part of the
  photo and the frame is labelled SAMPLE. Plain CSS; paused while the hero is
  off screen.
- **Dashboard:** labelled SAMPLE FEED. The drone box follows a wandering
  drone, the plane drifts across, the confidences settle around their sample
  values, the tracks draw in, and a sweep passes over the radar. Loads near
  the panel and only runs while it is visible.
- **Scroll reveals:** headings, cards and the timeline fade up once.
- **Reduced motion:** everything is shown finished and still.
- **Privacy:** fonts, scripts and images are served from the site itself.
  The only third-party request is the optional GoatCounter visit counter.

---

## Performance

Lighthouse, mobile preset (simulated slow 4G and a 4× slower CPU), measured
against the production build before the mockup redesign, which removed
Three.js and GSAP (about 670 KB of script; the page now loads about 6 KB).
Re-run it on the live URL to get current numbers:

| Performance | Accessibility | Best practices | SEO |
| :---------: | :-----------: | :------------: | :-: |
|   97 – 99   |      100      |      100       | 100 |

FCP 1.4–1.5 s · LCP 1.8–1.9 s · TBT 120–150 ms · CLS 0

Lighthouse runs Chrome without a GPU, so it gets the static images, not the
3D views. On a real phone, the 3D loads after the first paint, so first
paint and LCP stay the same. To measure on real hardware, run PageSpeed
Insights (pagespeed.web.dev) on the live URL.
