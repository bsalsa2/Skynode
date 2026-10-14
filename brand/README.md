# Varn brand

Varn brand system v1.0. **Varn** is the product; **Varn Labs** is only an
organization label (footer, copyright line, site name), not a company.

## Source of truth

- `assets/varn_design_tokens.css`: colours, type stacks, spacing and radii.
  The apps copy these into `brain/dashboard/graphite.css`, which both the live
  dashboard and the website load. One token was added: `--varn-amber`
  (`#E0A84A`), the only alert colour, for possible drones.
- `VARN_Brand_Guide.pdf` / `.docx`: the guide (palette, type, voice, do/don't).
- `src/build_brand.py`: builds every logo file below. Edit it, not the SVGs.

## Logo files

| File | What |
|---|---|
| `varn_mark.svg` | The mark, `fill="currentColor"`. Use this in code. |
| `varn_mark_on-dark.svg` / `varn_mark_on-light.svg` | Bone mark for charcoal/night, ink mark for bone/white |
| `varn_mark_small*.svg` | Simplified mark for about 24 px wide (12 px tall) and below |
| `varn_wordmark*.svg` | VARN in Space Grotesk 500, tracking +0.62 em, outlined |
| `varn_lockup_stacked_on-{dark,light}.svg` | Mark over wordmark, the reference's proportions |
| `varn_lockup_horizontal_on-{dark,light}.svg` | Mark beside wordmark |
| `mark-compare.png` | The approved reference next to these files at 16/32/64/256 px, plus an overlay |

The kit's own SVGs in `assets/` (thin strokes) don't match the approved logo;
use the files above instead. `assets/varn_original_logo_reference.png` is the
approved logo.

**The mark** is traced from that reference as three filled quadrilaterals: two
thick, tapering outer blades and the short inner blade. Edges were fitted at 8x
resolution, so the outline sits on the reference to within about a pixel at
512 px (see the overlay in `mark-compare.png`).

**The small mark.** Below about 24 px wide the gap between the inner blade and
the right blade is under one pixel and the two merge. The small mark keeps the
two outer blades, slightly heavier, with a wider gap at the base. It adds no
new parts. The website switches to it automatically below 24 px.

**The wordmark** uses Space Grotesk's normal A (with its crossbar), not the
reference's open Λ. It is converted to paths, so it never depends on an
installed font.

## Rebuild

```
pip install fonttools brotli cairosvg pillow numpy
python brand/src/build_brand.py            # logo files, mark-compare.png, web/src/logo.js
python brand/src/build_brand.py --icons    # also favicons, app icons, og-image, README banner
```

Fonts come from `brain/dashboard/fonts/` (Space Grotesk and Inter, SIL OFL).

## Still open

- USPTO search for "Varn" (classes 9 and 42): see `docs/TODO-name.md`.
- The website is at `tryvarn.com`.
