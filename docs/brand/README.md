# Varn brand v6

Charcoal + Bronze + Split. Source of truth for tokens is
`brain/dashboard/graphite.css` (loaded by both the website and the live
dashboard); `tokens.json` here is the same set for other tools.

- `symbol-split-*.svg`, `lockup-*.svg`, `favicon.svg`: the recommended mark.
  Lockups reference Michroma by name; outline the text before using them
  where the font is not installed.
- Wordmark: VARN, Michroma 400, letter-spacing +0.22em.
- Logo dot is always bronze (`#CF8A52` dark, `#94521F` light), never a status colour.
- Status: green circle = confirmed aircraft, amber square = possible drone,
  violet ring = no ADS-B match. Always colour + shape + word.
- Any simulated visual carries a visible SAMPLE tag. Never use the words
  missile, kill, strike or defeat (`npm run check` in `web/` enforces this on
  the site copy).
- Exports: `docs/varn_banner.png` (1280x640), `web/public/og-image.png`
  (1200x630), favicon set in `web/public/`.
