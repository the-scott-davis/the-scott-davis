"""Turn a photograph into a small, palette-limited pixel-art image.

Characters top out at roughly one tone per cell, which is not enough resolution
for a face to be *identifiable* -- you get a person-shaped smudge.  Pixels carry
colour, so the same 60-odd columns become an obvious likeness.

The output is a PNG at native art resolution (e.g. 64x81), committed to the
repo.  ``profilecard.render`` reads it back and emits one ``<rect>`` per run of
same-coloured pixels, so the card stays a self-contained SVG with no embedded
bitmap.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class PixelOptions:
    """Every knob the converter exposes.  All of these map 1:1 to CLI flags."""

    width: int = 64
    height: int | None = None  # derived from the source aspect when omitted

    # Framing
    crop: tuple[float, float, float, float] | None = None  # l, t, r, b in 0..1

    # Colour
    palette: int = 32  # how many colours to quantise to; fewer reads as flatter art
    dither: bool = False  # dithering fights the flat-region look, so off by default
    saturation: float = 1.15
    contrast: float = 1.08
    brightness: float = 1.0

    # Detail
    sharpen: float = 0.0  # unsharp-mask strength applied before downsampling


def _apply_crop(img: Image.Image, crop: tuple[float, float, float, float]) -> Image.Image:
    left, top, right, bottom = crop
    w, h = img.size
    box = (int(left * w), int(top * h), int(right * w), int(bottom * h))
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError(f"crop {crop} is empty")
    return img.crop(box)


def image_to_pixels(source: str | Path | Image.Image, opts: PixelOptions) -> Image.Image:
    """Return a small RGB image -- one source pixel per art pixel."""
    img = source if isinstance(source, Image.Image) else Image.open(source)
    img = img.convert("RGB")

    if opts.crop:
        img = _apply_crop(img, opts.crop)

    if opts.sharpen > 0:
        # Before the resize, so detail survives averaging rather than being
        # sharpened back out of mush afterwards.
        img = img.filter(
            ImageFilter.UnsharpMask(radius=2, percent=int(opts.sharpen * 100), threshold=2)
        )

    height = opts.height or max(1, round(opts.width * img.height / img.width))
    small = img.resize((opts.width, height), Image.LANCZOS)

    if opts.brightness != 1.0:
        small = ImageEnhance.Brightness(small).enhance(opts.brightness)
    if opts.contrast != 1.0:
        small = ImageEnhance.Contrast(small).enhance(opts.contrast)
    if opts.saturation != 1.0:
        small = ImageEnhance.Color(small).enhance(opts.saturation)

    if opts.palette and opts.palette > 1:
        dither = Image.Dither.FLOYDSTEINBERG if opts.dither else Image.Dither.NONE
        small = small.quantize(
            colors=opts.palette, method=Image.MEDIANCUT, dither=dither
        ).convert("RGB")

    return small


# ── Reading the committed PNG back for rendering ────────────────────────────

@dataclass
class Box:
    """A solid rectangle of one colour, in art-pixel units."""

    x: int
    y: int
    w: int
    h: int
    color: str


def _merge_vertical(boxes: list[Box]) -> list[Box]:
    """Stack boxes sitting directly on top of each other with the same x/width."""
    open_boxes: dict[tuple[int, int, str], Box] = {}
    out: list[Box] = []
    for box in boxes:
        key = (box.x, box.w, box.color)
        above = open_boxes.get(key)
        if above is not None and above.y + above.h == box.y:
            above.h += box.h
            continue
        open_boxes[key] = box
        out.append(box)
    return out


def load_boxes(path: str | Path) -> tuple[int, int, list[Box]]:
    """Read a pixel-art PNG and reduce it to solid rectangles.

    Rows are run-length encoded, then vertically adjacent runs of the same width
    and colour are stacked.  On a typical portrait this turns ~5,000 pixels into
    ~2,500 rectangles, which is the difference between a reasonable SVG and a
    needlessly enormous one.
    """
    img = Image.open(path).convert("RGB")
    w, h = img.size
    px = img.load()

    runs: list[Box] = []
    for y in range(h):
        start = 0
        current = px[0, y]
        for x in range(1, w + 1):
            pixel = px[x, y] if x < w else None
            if pixel != current:
                runs.append(Box(start, y, x - start, 1, "#%02x%02x%02x" % current))
                start, current = x, pixel
    return w, h, _merge_vertical(runs)


def boxes_to_paths(boxes: list[Box]) -> list[tuple[str, str]]:
    """Group boxes by colour into ``(colour, path_data)`` pairs.

    One ``<path>`` per colour beats one ``<rect>`` per box by roughly 3x on
    bytes: ``M12 30h3v2h-3z`` against ``<rect x="12" y="30" width="3" height="2"/>``.
    """
    by_color: dict[str, list[str]] = {}
    for b in boxes:
        by_color.setdefault(b.color, []).append(f"M{b.x} {b.y}h{b.w}v{b.h}h-{b.w}z")
    return [(color, "".join(parts)) for color, parts in by_color.items()]
