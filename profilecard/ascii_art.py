"""Turn a photograph into a block of monospace characters.

The output is a plain ``.txt`` file: one line per character row, no trailing
whitespace, no escape codes.  ``profilecard.render`` drops it straight into the
SVG, so whatever you see in the terminal is what lands on your profile.

Run it with ``python -m profilecard.portrait`` (see ``--help``) or call
:func:`image_to_ascii` directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

# Character ramps run dark -> light.  Pick one with --ramp, or pass your own
# string of characters.  The first character is "empty", the last is "solid".
RAMPS = {
    "blocks": " ░▒▓█",
    "shades": " .░▒▓█",
    "classic": " .:-=+*#%@",
    "minimal": " .:oO@",
    "dots": " .`',·:;!ilI|",
    "detailed": " .'`^\",:;Il!i~+_-?][}{1)(|/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    # Derived by rendering every printable ASCII character in a monospace font,
    # measuring what fraction of its cell it inks, and sampling that range at
    # even intervals -- so each step up the ramp is an even step in tone. Hand-
    # written ramps bunch up in the midtones. See docs/CUSTOMIZING.md.
    "measured": " `'.-,:\"r|cxYFe4$UHR0M@N",
    "measured32": " `'.-,_:~^;+<ivtYn23ZPGU&#Q0B@NM",
    # Near-binary, for logos and other flat high-contrast art.
    "silhouette": " .:-+*#%@",
}

# A character cell is taller than it is wide.  This is width / height for the
# default 16px font on a 20px line -- override it if you change the geometry.
DEFAULT_CELL_ASPECT = 8.8 / 20.0


@dataclass
class PortraitOptions:
    """Every knob the converter exposes.  All of these map 1:1 to CLI flags."""

    width: int = 44
    height: int | None = None  # derived from the source aspect when omitted
    cell_aspect: float = DEFAULT_CELL_ASPECT
    ramp: str = "classic"
    invert: bool = False

    # Framing
    crop: tuple[float, float, float, float] | None = None  # l, t, r, b in 0..1

    # Tone
    black_point: float = 0.0  # input level mapped to "empty"
    white_point: float = 1.0  # input level mapped to "solid"
    gamma: float = 1.0  # <1 brightens midtones, >1 darkens them
    autocontrast: float | None = None  # percent clipped from each end

    # Detail
    sharpen: float = 0.0  # unsharp-mask strength, 0 disables

    # Background knockout
    vignette: float = 0.0  # 0 none, 1 fully dark corners
    vignette_power: float = 2.0
    floor: float | None = None  # levels below this snap to "empty"

    trim: bool = True  # drop fully blank rows/columns from the edges
    # When inverting for a light card, the faintest ink level to still draw --
    # keeps highlights (a forehead, a shirt) from vanishing into the page.
    ink_floor: float = 0.12

    def ramp_chars(self) -> str:
        chars = RAMPS.get(self.ramp, self.ramp)
        if len(chars) < 2:
            raise ValueError("ramp needs at least 2 characters")
        return chars


def _apply_crop(img: Image.Image, crop: tuple[float, float, float, float]) -> Image.Image:
    left, top, right, bottom = crop
    w, h = img.size
    box = (int(left * w), int(top * h), int(right * w), int(bottom * h))
    if box[2] <= box[0] or box[3] <= box[1]:
        raise ValueError(f"crop {crop} is empty")
    return img.crop(box)


def _target_size(img: Image.Image, opts: PortraitOptions) -> tuple[int, int]:
    if opts.height:
        return opts.width, opts.height
    w, h = img.size
    rows = round(opts.width * (h / w) * opts.cell_aspect)
    return opts.width, max(1, rows)


def _vignette(img: Image.Image, opts: PortraitOptions) -> Image.Image:
    """Fade the corners toward black so a busy background stops competing."""
    if opts.vignette <= 0:
        return img
    w, h = img.size
    cx, cy = (w - 1) / 2, (h - 1) / 2
    px = img.load()
    for y in range(h):
        dy = (y - cy) / cy if cy else 0.0
        for x in range(w):
            dx = (x - cx) / cx if cx else 0.0
            # Normalised elliptical distance from the centre, clamped to 1.
            r = min(1.0, (dx * dx + dy * dy) ** 0.5)
            falloff = 1.0 - opts.vignette * (r**opts.vignette_power)
            px[x, y] = max(0, min(255, int(px[x, y] * falloff)))
    return img


def _levels(value: float, opts: PortraitOptions) -> float:
    lo, hi = opts.black_point, opts.white_point
    if hi <= lo:
        raise ValueError("white_point must be greater than black_point")
    v = (value - lo) / (hi - lo)
    v = max(0.0, min(1.0, v))
    if opts.gamma != 1.0:
        v = v ** opts.gamma
    if opts.floor is not None and v < opts.floor:
        v = 0.0
    return v


def _trim(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return lines
    lead = min((len(l) - len(l.lstrip(" ")) for l in lines if l.strip()), default=0)
    return [l[lead:].rstrip() for l in lines]


def image_to_ascii(source: str | Path | Image.Image, opts: PortraitOptions) -> str:
    """Render ``source`` as a block of text using ``opts``."""
    img = source if isinstance(source, Image.Image) else Image.open(source)
    img = img.convert("RGB")

    if opts.crop:
        img = _apply_crop(img, opts.crop)

    cols, rows = _target_size(img, opts)

    if opts.sharpen > 0:
        # Sharpen before downsampling: fine detail survives the resize instead
        # of being averaged into mush.
        img = img.filter(
            ImageFilter.UnsharpMask(radius=2, percent=int(opts.sharpen * 100), threshold=2)
        )

    gray = img.convert("L").resize((cols, rows), Image.LANCZOS)

    if opts.autocontrast is not None:
        gray = ImageOps.autocontrast(gray, cutoff=opts.autocontrast)

    gray = _vignette(gray, opts)

    chars = opts.ramp_chars()
    last = len(chars) - 1
    pixels = gray.load()
    lines: list[str] = []
    for y in range(rows):
        row = []
        for x in range(cols):
            v = _levels(pixels[x, y] / 255.0, opts)
            # `v` is photo brightness; `ink` is how much character to draw.
            # On a dark card ink follows brightness.  On a light card it runs
            # the other way -- but only *inside* the subject, or the knocked-out
            # background would come back as a solid block of ink.
            if opts.invert:
                ink = 0.0 if v <= 0.0 else max(opts.ink_floor, 1.0 - v)
            else:
                ink = v
            row.append(chars[round(ink * last)])
        lines.append("".join(row).rstrip())

    return "\n".join(_trim(lines) if opts.trim else lines)
