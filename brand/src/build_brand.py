"""Build the Varn logo files from one source of truth (this script).

    pip install fonttools brotli cairosvg pillow numpy
    python brand/src/build_brand.py

Writes, in brand/:
    varn_mark.svg                  the mark, fill = currentColor
    varn_mark_on-dark.svg          bone mark, for charcoal/night backgrounds
    varn_mark_on-light.svg         ink mark, for bone/white backgrounds
    varn_mark_small*.svg           simplified mark for 20 px and below
    varn_wordmark*.svg             VARN in Space Grotesk, outlined (no font needed)
    varn_lockup_{stacked,horizontal}_on-{dark,light}.svg
    mark-compare.png               the reference next to these files at 16/32/64/256 px

and web/src/logo.js (the same paths, for the website's inline SVG).

With --icons it also rebuilds the icons and share images that use the mark:
    web/public/favicon.svg, favicon-32.png, favicon.ico, apple-touch-icon.png,
    icon-512.png, og-image.png; brain/dashboard/favicon.svg; docs/varn_banner.png

THE MARK. Traced from assets/varn_original_logo_reference.png: three filled
quadrilaterals (two outer blades and the short inner blade). The vertices are
the reference's edge lines, fitted at 8x with sub-pixel accuracy and rounded to
0.5 units, in the reference's own pixels (the mark is 391.5 x 194 there). The
outer silhouette is symmetric about x = 195.75; the blades taper towards the
bottom, the right one a little more, to make room for the inner blade. That is
how the reference is drawn, so it is kept.

THE SMALL MARK. Below about 24 px the gap between the inner blade and the right
blade is under one pixel, so the inner blade merges into it and the mark reads
as a blurred V. The small mark keeps the two outer blades (no new parts),
thickens them slightly and widens the gap at the base so they stay separate.
"""
import io
from pathlib import Path

BRAND = Path(__file__).resolve().parent.parent
REPO = BRAND.parent
FONT = REPO / "brain" / "dashboard" / "fonts" / "space-grotesk-latin-500-normal.woff2"
REFERENCE = BRAND / "assets" / "varn_original_logo_reference.png"
REFERENCE_MARK_BOX = (641, 245, 1031, 439)       # the mark's pixels in the reference image

# From assets/varn_design_tokens.css
BONE, INK, CHARCOAL, NIGHT, FOG, STEEL = "#F4F3EF", "#17212B", "#0B0F14", "#111820", "#A7B3BD", "#4B5B6B"
INTER = REPO / "brain" / "dashboard" / "fonts" / "inter-latin-500-normal.woff2"

# ---- Mark ---------------------------------------------------------------------------

MARK_W, MARK_H = 391.5, 194
MARK = (
    [(0, 0), (58.5, 0), (177.5, 142), (177.5, 194)],             # left blade
    [(391.5, 0), (332.5, 0), (214, 159), (214, 194)],            # right blade
    [(285, 32.5), (223, 55.5), (171.5, 106), (202, 143)],        # inner blade
)
# 20 px and below: outer blades only, a touch heavier, with a wider gap at the base.
SMALL = (
    [(0, 0), (76, 0), (172, 128), (172, 194)],
    [(391.5, 0), (315.5, 0), (219.5, 128), (219.5, 194)],
)


def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".")


def polygons_path(polys, dx=0.0, dy=0.0, scale=1.0):
    return "".join(
        "M" + " ".join(f"{fmt(dx + x * scale)} {fmt(dy + y * scale)}" for x, y in poly) + "Z"
        for poly in polys)


def svg(width, height, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height)}" '
            f'role="img" aria-label="{title}"><title>{title}</title>{body}</svg>\n')


# ---- Wordmark -----------------------------------------------------------------------

TRACKING = 0.62     # em. Wide, like the reference (whose gaps are about one cap height)


def text_path(text, font_file=FONT, tracking=0.0):
    """Outlines of `text` in `font_file`, cap height = the font's cap height (units), y down,
    ink starting at x = 0. `tracking` is extra space between letters, in em.
    Returns (path d, ink width, cap height)."""
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont

    font = TTFont(font_file)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    upm, cap = font["head"].unitsPerEm, font["OS/2"].sCapHeight
    names = [cmap[ord(ch)] for ch in text]
    first = BoundsPen(glyphs)
    glyphs[names[0]].draw(first)
    x, left = 0.0, (first.bounds or (0,))[0]
    pen = SVGPathPen(glyphs, ntos=lambda v: fmt(v))
    right = 0.0
    for i, name in enumerate(names):
        glyph = glyphs[name]
        glyph.draw(TransformPen(pen, (1, 0, 0, -1, x - left, cap)))
        bounds = BoundsPen(glyphs)
        glyph.draw(bounds)
        right = x - left + (bounds.bounds[2] if bounds.bounds else glyph.width)
        x += glyph.width + (tracking * upm if i < len(names) - 1 else 0)
    return pen.getCommands(), right, cap


def wordmark_path():
    """VARN in Space Grotesk 500, cap height = 700 units."""
    return text_path("VARN", FONT, TRACKING)


def group(path_d, fill, dx=0.0, dy=0.0, scale=1.0):
    transform = f' transform="translate({fmt(dx)} {fmt(dy)}) scale({fmt(scale)})"' \
        if (dx, dy, scale) != (0, 0, 1) else ""
    return f'<path fill="{fill}"{transform} d="{path_d}"/>'


# ---- Files --------------------------------------------------------------------------

def build():
    files = {}
    mark_d, small_d = polygons_path(MARK), polygons_path(SMALL)
    for suffix, fill in (("", "currentColor"), ("_on-dark", BONE), ("_on-light", INK)):
        files[f"varn_mark{suffix}.svg"] = svg(MARK_W, MARK_H, group(mark_d, fill), "Varn")
        files[f"varn_mark_small{suffix}.svg"] = svg(MARK_W, MARK_H, group(small_d, fill), "Varn")

    word_d, word_w, cap = wordmark_path()
    for suffix, fill in (("", "currentColor"), ("_on-dark", BONE), ("_on-light", INK)):
        files[f"varn_wordmark{suffix}.svg"] = svg(word_w, cap, group(word_d, fill), "Varn")

    # Stacked, in the reference's proportions: cap height = 0.485 x mark height,
    # gap = 0.45 x mark height, both centred. Clear space: one blade width (58.5) all round.
    pad = 58.5
    cap_h = 0.485 * MARK_H
    k = cap_h / cap
    ww = word_w * k
    width = max(MARK_W, ww) + 2 * pad
    gap = 0.45 * MARK_H
    height = MARK_H + gap + cap_h + 2 * pad
    for name, fill in (("on-dark", BONE), ("on-light", INK)):
        body = (group(mark_d, fill, (width - MARK_W) / 2, pad)
                + group(word_d, fill, (width - ww) / 2, pad + MARK_H + gap, k))
        files[f"varn_lockup_stacked_{name}.svg"] = svg(width, height, body, "Varn")

    # Horizontal: mark 1.6 x cap height tall, one cap height of space, centred vertically.
    cap_h = 70.0
    mk = 1.6 * cap_h / MARK_H
    k = cap_h / cap
    mw, mh, ww = MARK_W * mk, MARK_H * mk, word_w * k
    pad = 58.5 * mk
    gap = 1.25 * cap_h
    width = pad + mw + gap + ww + pad
    height = mh + 2 * pad
    for name, fill in (("on-dark", BONE), ("on-light", INK)):
        body = (group(mark_d, fill, pad, pad, mk)
                + group(word_d, fill, pad + mw + gap, pad + (mh - cap_h) / 2, k))
        files[f"varn_lockup_horizontal_{name}.svg"] = svg(width, height, body, "Varn")

    for name, text in files.items():
        (BRAND / name).write_text(text)
    (REPO / "web" / "src" / "logo.js").write_text(
        "// Generated by brand/src/build_brand.py from the master SVGs in brand/. Don't edit.\n"
        f"export const MARK_VIEWBOX = '0 0 {fmt(MARK_W)} {fmt(MARK_H)}';\n"
        f"export const MARK_PATH = '{mark_d}';\n"
        f"export const MARK_SMALL_PATH = '{small_d}';\n"
        f"export const WORDMARK_VIEWBOX = '0 0 {fmt(word_w)} {fmt(cap)}';\n"
        f"export const WORDMARK_PATH = '{word_d}';\n")
    return files


# ---- Comparison sheet ---------------------------------------------------------------

def render(svg_text, width):
    import cairosvg
    from PIL import Image
    png = cairosvg.svg2png(bytestring=svg_text.encode(), output_width=width)
    return Image.open(io.BytesIO(png)).convert("RGBA")


def compare_sheet(files):
    from PIL import Image, ImageDraw, ImageFont

    sizes = (16, 32, 64, 256)
    zoom = 8                            # pixel-for-pixel enlargement of the 16 and 32 px versions
    ref = Image.open(REFERENCE).convert("L")
    x0, y0, x1, y1 = REFERENCE_MARK_BOX
    ref_mark = ref.crop((x0, y0, x1 + 1, y1 + 1))

    def reference_at(width):
        h = round(width * ref_mark.height / ref_mark.width)
        alpha = ref_mark.resize((width, h), Image.LANCZOS).point(lambda v: max(0, min(255, (v - 32) * 255 // 203)))
        tile = Image.new("RGBA", alpha.size, BONE)
        tile.putalpha(alpha)
        return tile

    rows = (("Reference (PNG)", reference_at),
            ("varn_mark.svg", lambda w: render(files["varn_mark_on-dark.svg"], w)),
            ("varn_mark_small.svg (20 px and below)", lambda w: render(files["varn_mark_small_on-dark.svg"], w)))
    cell = 256 + 48
    label_w = 400
    row_h = 256 * MARK_H / MARK_W + 64
    zoom_w = 16 * zoom + 32 * zoom + 72
    W = label_w + cell * len(sizes) + zoom_w
    H = int(80 + row_h * len(rows) + 300)
    sheet = Image.new("RGBA", (W, H), CHARCOAL)
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 18)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font = small = ImageFont.load_default()
    fog = "#A7B3BD"
    for i, s in enumerate(sizes):
        draw.text((label_w + i * cell, 28), f"{s} px wide", fill=fog, font=font)
    draw.text((label_w + len(sizes) * cell, 28), f"16 and 32 px, enlarged {zoom}x", fill=fog, font=font)
    for r, (label, make) in enumerate(rows):
        top = 80 + r * row_h
        draw.text((24, top + 40), label, fill=BONE, font=font)
        for i, s in enumerate(sizes):
            tile = make(s)
            sheet.alpha_composite(tile, (int(label_w + i * cell), int(top + (256 * MARK_H / MARK_W - tile.height) / 2)))
        x = label_w + len(sizes) * cell
        for s in (16, 32):
            tile = make(s)
            flat = Image.new("RGBA", tile.size, CHARCOAL)
            flat.alpha_composite(tile)
            big = flat.resize((s * zoom, tile.height * zoom), Image.NEAREST)
            sheet.alpha_composite(big, (int(x), int(top)))
            x += s * zoom + 36

    # Overlay at 512 px: reference in sage, the SVG's edges in amber, to show the fit.
    top = int(80 + row_h * len(rows)) + 10
    width = 512
    ref_big = ref_mark.resize((width, round(width * ref_mark.height / ref_mark.width)), Image.LANCZOS)
    base = Image.new("RGBA", ref_big.size, CHARCOAL)
    base.paste(Image.new("RGBA", ref_big.size, "#7A8B7E"), (0, 0), ref_big)
    outline = files["varn_mark.svg"].replace('fill="currentColor"', 'fill="none" stroke="#E0A84A" stroke-width="1.6"')
    base.alpha_composite(render(outline, width).resize(base.size))
    sheet.alpha_composite(base, (label_w, top))
    draw.text((24, top + 40), "Fit at 512 px", fill=BONE, font=font)
    draw.text((24, top + 70), "sage: reference\namber: SVG edges", fill=fog, font=small)
    out = BRAND / "mark-compare.png"
    sheet.convert("RGB").save(out, optimize=True)
    return out


# ---- Icons and share images ---------------------------------------------------------

def app_icon(size_units=512, small=False, radius=0.1875):
    """Bone mark centred on a charcoal rounded square (the app icon)."""
    s = size_units
    w = 0.66 * s
    k = w / MARK_W
    dx, dy = (s - w) / 2, (s - MARK_H * k) / 2 + 0.02 * s
    path = polygons_path(SMALL if small else MARK, dx, dy, k)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">'
            f'<rect width="{s}" height="{s}" rx="{fmt(radius * s)}" fill="{CHARCOAL}"/>'
            f'<path fill="{BONE}" d="{path}"/></svg>\n')


def share_image(width, height, headline_lines, caption):
    """Charcoal card: horizontal lockup, headline, caption, and the mark in a night tile."""
    m = 0.07 * width                                 # margin
    parts = [f'<rect width="{width}" height="{height}" fill="{CHARCOAL}"/>']
    # Lockup, top left
    cap_h = 0.02 * width
    mk = 1.6 * cap_h / MARK_H
    word_d, word_w, cap = wordmark_path()
    parts.append(group(polygons_path(MARK), BONE, m, m, mk))
    parts.append(group(word_d, BONE, m + MARK_W * mk + 1.25 * cap_h, m + (MARK_H * mk - cap_h) / 2, cap_h / cap))
    # Headline: Space Grotesk 500, tight
    head_cap = 0.05 * width
    y = height * 0.36
    for line in headline_lines:
        d, _, hcap = text_path(line, FONT, -0.025)
        parts.append(group(d, BONE, m, y, head_cap / hcap))
        y += head_cap * 1.55
    # Caption: Inter 500, uppercase, tracked
    d, _, ccap = text_path(caption.upper(), INTER, 0.16)
    parts.append(group(d, FOG, m, height - m - 0.011 * width, 0.011 * width / ccap))
    # Mark tile, right
    tile = 0.3 * width
    tx, ty = width - m - tile, (height - tile) / 2
    parts.append(f'<rect x="{fmt(tx)}" y="{fmt(ty)}" width="{fmt(tile)}" height="{fmt(tile)}" '
                 f'rx="{fmt(0.1875 * tile)}" fill="{NIGHT}" stroke="{STEEL}" stroke-opacity="0.6"/>')
    w = 0.66 * tile
    k = w / MARK_W
    parts.append(group(polygons_path(MARK), BONE, tx + (tile - w) / 2, ty + (tile - MARK_H * k) / 2 + 0.02 * tile, k))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">'
            + "".join(parts) + "</svg>\n")


def png(svg_text, width, path):
    render(svg_text, width).save(path, optimize=True)


def build_icons():
    from PIL import Image
    public = REPO / "web" / "public"
    small_icon = app_icon(32, small=True, radius=0.22)
    for target in (public / "favicon.svg", REPO / "brain" / "dashboard" / "favicon.svg"):
        target.write_text(small_icon)
    png(small_icon, 32, public / "favicon-32.png")
    png(app_icon(180, radius=0.0), 180, public / "apple-touch-icon.png")    # iOS rounds it itself
    png(app_icon(512), 512, public / "icon-512.png")
    icos = [render(small_icon, n) for n in (16, 32)] + [render(app_icon(48), 48)]
    icos[-1].save(public / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)],
                  append_images=icos[:-1])
    png(share_image(1200, 630, ["A clear view of", "your airspace."],
                    "Passive detection \u00b7 drones and aircraft"), 1200, public / "og-image.png")
    png(share_image(1280, 640, ["Watch the sky."],
                    "Detection only  +  ~$113 in sensing parts  +  not yet on real hardware"),
        1280, REPO / "docs" / "varn_banner.png")
    Image.open(public / "favicon.ico")      # fails loudly if the .ico is broken


if __name__ == "__main__":
    import sys
    built = build()
    print("wrote", ", ".join(sorted(built)))
    print("wrote", compare_sheet(built).relative_to(REPO))
    if "--icons" in sys.argv:
        build_icons()
        print("wrote icons and share images")
