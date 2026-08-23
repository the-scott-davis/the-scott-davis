"""Tell you, before you shoot or commit to an image, how it will survive ASCII.

Characters carry tone and nothing else, so what matters is not how much contrast
an image *has* but how much of it is **local brightness variation inside the
subject**.  Those two come apart badly.  A photo can span the full tonal range,
look vivid, and still be almost flat across the face -- and a busy background
will happily supply contrast that does nothing for the portrait.

So this measures one thing: within the region you actually intend to render, how
far apart in brightness are neighbouring areas.  That is the number that decides
whether an ASCII portrait shows a face or a smudge.

Thresholds are calibrated against a small sample -- treat the number as the
signal and the verdict as a hint.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

# Below this many source pixels per character cell, downsampling loses detail.
# Above it, extra resolution is discarded -- a bigger file buys you nothing.
PX_PER_CELL_FLOOR = 3.0

# Edge strength: the mean of the strongest 5% of brightness gaps between
# neighbouring areas of the subject, out of 255.
#
# Not the median, and not a lower percentile. What decides an ASCII render is
# whether strong edges *exist* to draw the subject with, not whether most of the
# frame is busy. A logo is mostly flat with a few hard edges and renders
# beautifully -- a median scores that near zero. A plain shape's perimeter can be
# under 5% of all measurements, which sinks a 90th percentile too. Averaging the
# top 5% survives both, and one bright speck cannot carry it the way a max can.
CONTRAST_GOOD = 130
CONTRAST_POOR = 100


def _luma(c) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


@dataclass
class Report:
    width: int
    height: int
    px_per_cell: float
    local_median: float  # typical brightness step between neighbouring areas
    edge_strength: float  # mean of the strongest 5% -- what the verdict turns on
    background_variation: float
    crop: tuple[float, float, float, float]

    @property
    def verdict(self) -> str:
        if self.edge_strength >= CONTRAST_GOOD:
            return "ascii"
        if self.edge_strength >= CONTRAST_POOR:
            return "marginal"
        return "pixel"


def analyze(source, crop=None, columns: int = 72, patches: int = 20) -> Report:
    """Measure local brightness contrast inside ``crop`` (0..1 fractions)."""
    img = source if isinstance(source, Image.Image) else Image.open(source)
    img = img.convert("RGB")
    w, h = img.size

    crop = crop or (0.15, 0.05, 0.85, 0.85)  # a reasonable head-and-shoulders guess
    subject = img.crop(
        (int(crop[0] * w), int(crop[1] * h), int(crop[2] * w), int(crop[3] * h))
    )

    grid = subject.resize((patches, patches), Image.LANCZOS)
    at = lambda x, y: _luma(grid.getpixel((x, y)))

    gaps = []
    for y in range(patches):
        for x in range(patches):
            for dx, dy in ((1, 0), (0, 1)):
                if x + dx < patches and y + dy < patches:
                    gaps.append(abs(at(x, y) - at(x + dx, y + dy)))
    gaps.sort()
    median = gaps[len(gaps) // 2] if gaps else 0.0
    strongest = gaps[int(len(gaps) * 0.95) :] or [0.0]
    edge_strength = sum(strongest) / len(strongest)

    # Whatever falls outside the crop is background; how varied it is predicts
    # how much vignette and floor tuning it will take to knock it out.
    edge = img.resize((patches, patches), Image.LANCZOS)
    border = [
        _luma(edge.getpixel((x, y)))
        for y in range(patches)
        for x in range(patches)
        if x in (0, patches - 1) or y in (0, patches - 1)
    ]
    mean = sum(border) / len(border)
    variation = (sum((v - mean) ** 2 for v in border) / len(border)) ** 0.5

    return Report(
        width=w,
        height=h,
        px_per_cell=(crop[2] - crop[0]) * w / columns,
        local_median=median,
        edge_strength=edge_strength,
        background_variation=variation,
        crop=crop,
    )


def format_report(r: Report) -> str:
    enough = r.px_per_cell >= PX_PER_CELL_FLOOR
    lines = [
        f"  size                     {r.width} x {r.height}",
        f"  source px per cell       {r.px_per_cell:.1f}"
        + (f"   (plenty -- {r.px_per_cell / PX_PER_CELL_FLOOR:.1f}x what the grid can use)"
           if enough else "   <- too low, shoot larger"),
        "",
        f"  edge strength            {r.edge_strength:.0f} / 255"
        f"   (need {CONTRAST_GOOD}+ -- this decides it)",
        f"  typical local contrast   {r.local_median:.0f} / 255",
        f"  background variation     {r.background_variation:.0f}"
        + ("   <- busy, expect to fight it" if r.background_variation > 25 else "   (clean)"),
        "",
    ]
    if r.verdict == "ascii":
        lines.append("  VERDICT: good for mode: ascii.")
    elif r.verdict == "marginal":
        lines += [
            "  VERDICT: marginal for ascii -- expect a soft, low-detail result.",
            "  The fix is light, not resolution: one strong source off to the side.",
        ]
    else:
        lines += [
            "  VERDICT: too flat for ascii. It will render as a smudge.",
            "  Either use mode: pixel, or reshoot with hard directional lighting.",
            "  Resolution will not help -- this is a lighting problem.",
        ]
    return "\n".join(lines)
