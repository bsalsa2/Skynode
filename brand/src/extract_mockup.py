"""Cut the photography out of the approved homepage mockup (docs/design/home-mockup.webp)
for the website, removing the text and UI that is baked into the image.

    python brand/src/extract_mockup.py

Writes web/src/assets/{hero-sky,roadmap-peak,feed-sky}.webp.

Only the bright marks (letters, lines, dots) are painted out, found with a top-hat
filter, so the clouds around them survive; the solid buttons are the only
rectangles removed. The drone stays in the hero photo: the page draws the tracking
line, frame and crosshair over it in the mockup's own coordinates (1024 x 462).
The mockup is 1024 px wide, so every crop is upscaled 2x (Lanczos) with a light
sharpen; the page shades the photos, which hides most of the softness.
"""
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "docs" / "design" / "home-mockup.webp"
OUT = REPO / "web" / "src" / "assets"


def tophat_mask(img, box, k=9, thresh=18):
    """Pixels inside `box` much brighter than their neighbourhood (thin marks, text)."""
    x0, y0, x1, y1 = box
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    hat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    m = np.zeros(gray.shape, np.uint8)
    m[y0:y1, x0:x1] = (hat[y0:y1, x0:x1] > thresh).astype(np.uint8) * 255
    return m


def rects(img, boxes):
    m = np.zeros(img.shape[:2], np.uint8)
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] = 255
    return m


def clean(img, mask, grow=1, radius=4):
    mask = cv2.dilate(mask, np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8))
    return cv2.inpaint(img, mask, radius, cv2.INPAINT_TELEA)


def save(img, name, scale=2, quality=80):
    big = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
    blur = cv2.GaussianBlur(big, (0, 0), 1.2)
    sharp = cv2.addWeighted(big, 1.35, blur, -0.35, 0)
    cv2.imwrite(str(OUT / name), sharp, [cv2.IMWRITE_WEBP_QUALITY, quality])


def hero(im):
    img = im[0:462, 0:1024].copy()
    m = np.zeros(img.shape[:2], np.uint8)
    for box in [
        (55, 15, 240, 60), (330, 22, 655, 52),                            # logo, nav
        (60, 125, 118, 146), (60, 145, 430, 216), (60, 220, 345, 272),    # eyebrow, h1, sub
        (58, 416, 540, 442), (845, 403, 966, 440),                        # status row, tagline
    ]:
        m |= tophat_mask(img, box, k=15, thresh=22)
    m |= rects(img, [(64, 294, 220, 336), (232, 294, 350, 336), (886, 18, 968, 56)])  # buttons
    m |= tophat_mask(img, (0, 120, 1024, 462), k=7, thresh=14)          # track line, frame, divider
    m |= tophat_mask(img, (770, 0, 792, 462), k=9, thresh=8)            # the long vertical line
    m |= tophat_mask(img, (640, 180, 1010, 200), k=9, thresh=8)         # the horizontal line
    keep = np.zeros_like(m)
    cv2.circle(keep, (912, 300), 70, 255, -1)                            # the sun and its glow
    keep[170:210, 746:824] = 255                                         # the drone
    m[keep > 0] = 0
    save(clean(img, m), "hero-sky.webp")


def roadmap(im):
    img = im[1121:1386, 0:1024].copy()
    m = np.zeros(img.shape[:2], np.uint8)
    for box in [(60, 35, 395, 175), (676, 45, 860, 240)]:               # copy, timeline
        m |= tophat_mask(img, box, k=15, thresh=20)
    m |= rects(img, [(66, 190, 250, 230)])                               # the button
    save(clean(img, m, radius=5), "roadmap-peak.webp")


def feed(im):
    img = im[562:785, 480:815].copy()
    m = rects(img, [(84, 28, 132, 84), (200, 44, 262, 98), (32, 108, 52, 124)])  # boxes, far drone
    m |= tophat_mask(img, (0, 0, img.shape[1], img.shape[0]), k=7, thresh=20)    # labels, tracks
    save(clean(img, m), "feed-sky.webp", quality=78)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    source = cv2.imread(str(SRC))
    hero(source)
    roadmap(source)
    feed(source)
    print("wrote hero-sky.webp, roadmap-peak.webp, feed-sky.webp")
