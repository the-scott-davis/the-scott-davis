"""Render a fixed-size social banner from the same config and the same stats.

The card in :mod:`profilecard.render` sizes itself to its content.  A LinkedIn
cover cannot: the canvas is exactly 1584x396 and the content has to fit inside
it, so the relationship is inverted.  Here the block is laid out, measured, and
centred, and content that does not fit is an error rather than a clipped card.

Three constraints drive the layout, and none of them are obvious:

* **Mobile shows only the middle of the banner.**  The app crops the sides to
  roughly the centre 60% of the width, so a full-width composition loses its
  outer columns on a phone.  Everything is centred inside ``safe_width`` for
  that reason, not for symmetry.
* **The profile photo covers the bottom-left corner.**  On desktop it lands at
  about x 49..357, y 244..396 in these coordinates.  Nothing valuable belongs
  in that box.
* **Type is downscaled roughly 2x on desktop and 2.4x on a phone.**  16px, the
  card's size, arrives at 7px.  The banner sets its own, larger size and pays
  for it in rows.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from .config import BannerConfig, ConfigError, Theme
from .render import (
    STYLE_TAGS,
    _runs_to_tspans,
    build_columns,
    parse_markup,
    substitute,
    visible_length,
    xml_escape,
)

# Where the profile photo sits on desktop, in banner coordinates. Advisory: it
# is reported, not enforced, because a banner that merely clips the dim rail of
# a few rows is fine and refusing to render one would not be.
AVATAR_BOX = (49, 244, 357, 396)


def _lines_extent(x: int, y0: int, rows: int, banner: BannerConfig) -> tuple[int, int, int, int]:
    """Bounding box of a column of rows, for the avatar-overlap check."""
    return x, y0, x, y0 + rows * banner.line_height


def layout(banner: BannerConfig, values: dict[str, str]) -> dict:
    """Measure the whole composition and place it on the canvas.

    Separated from drawing so the geometry can be asserted in tests without
    parsing an SVG back out again.
    """
    card = banner.as_card()
    # build_columns also returns the card title, which a banner does not have:
    # as_card() blanks it so the headline below is measured at its own, larger
    # size instead of being folded into the body's column widths.
    _, columns = build_columns(card, values)

    cw, lh = banner.char_width, banner.line_height
    col_widths = [
        max((visible_length(line.runs) for line in col), default=0) for col in columns
    ]
    body_rows = max((len(col) for col in columns), default=0)
    body_cols = sum(col_widths) + banner.column_gutter * (len(columns) - 1)
    body_w = round(body_cols * cw)

    head_runs = parse_markup(substitute(banner.headline, values, "banner.headline"))
    sub_runs = parse_markup(substitute(banner.subhead, values, "banner.subhead"))
    link_runs = parse_markup(substitute(banner.link, values, "banner.link"))
    hcw = banner.headline_char_width
    # The link shares the subhead's line at the body size rather than the
    # headline's. Set beside a 26px headline it was the widest thing on the
    # canvas, and the whole block had to shrink to accommodate two lines of
    # text that were never the point.
    sub_w = round(
        (visible_length(sub_runs) + (2 if sub_runs and link_runs else 0)
         + visible_length(link_runs)) * cw
    )
    head_w = max(round(visible_length(head_runs) * hcw), sub_w)

    block_w = max(body_w, head_w)
    head_h = banner.headline_line_height if head_runs else 0
    if sub_runs or link_runs:
        head_h += lh
    block_h = head_h + (banner.headline_gap if head_h else 0) + body_rows * lh

    if block_w > banner.width or block_h > banner.height:
        raise ConfigError(
            f"banner: content is {block_w}x{block_h}px and does not fit the "
            f"{banner.width}x{banner.height} canvas -- drop a row, or lower "
            "banner.font_size / banner.line_height"
        )

    x0 = round((banner.width - block_w) / 2) + banner.offset_x
    y0 = round((banner.height - block_h) / 2)

    warnings: list[str] = []
    if block_w > banner.safe_width:
        over = block_w - banner.safe_width
        warnings.append(
            f"banner: content is {block_w}px wide against a {banner.safe_width}px "
            f"safe width -- about {over // 2}px ({over / 2 / cw:.1f} characters) "
            "will be cropped from each side on mobile"
        )
    # Only the leftmost column can reach the corner the photo covers, so the
    # check measures that column's own depth rather than the whole block's.
    _, ay0, ax1, _ = AVATAR_BOX
    body_top = y0 + head_h + (banner.headline_gap if head_h else 0)
    left_bottom = body_top + len(columns[0]) * lh if columns else body_top
    if x0 < ax1 and left_bottom > ay0:
        warnings.append(
            f"banner: the profile photo covers x<{ax1} below y={ay0}; the left "
            f"column runs to y={left_bottom} from x={x0}, so its lowest rows "
            f"lose about {(ax1 - x0) / cw:.1f} characters on desktop"
        )

    return {
        "columns": columns,
        "col_widths": col_widths,
        "head_runs": head_runs,
        "sub_runs": sub_runs,
        "link_runs": link_runs,
        "block_w": block_w,
        "block_h": block_h,
        "x0": x0,
        "y0": y0,
        "head_h": head_h,
        "warnings": warnings,
    }


def render(banner: BannerConfig, theme: Theme, values: dict[str, str]) -> tuple[str, list[str]]:
    """The banner SVG, plus any advisory warnings about where it will be cropped."""
    box = layout(banner, values)
    cw, lh = banner.char_width, banner.line_height
    x0, y0 = box["x0"], box["y0"]
    classes = {t: t for t in STYLE_TAGS}

    parts = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'width="{banner.width}px" height="{banner.height}px" '
        f'viewBox="0 0 {banner.width} {banner.height}" '
        f"font-family=\"ConsolasFallback,'DejaVu Sans Mono',Menlo,Consolas,monospace\" "
        f'font-size="{banner.font_size}px">',
        f"<title>{xml_escape(values.get('name', values['username']))}</title>",
        "<style>",
        "@font-face{src:local('Consolas');font-family:'ConsolasFallback';"
        "font-display:swap;size-adjust:109%;}",
        f".key{{fill:{theme.key};}}",
        f".value{{fill:{theme.value};}}",
        f".dim{{fill:{theme.dim};}}",
        f".add{{fill:{theme.add};}}",
        f".del{{fill:{theme.delete};}}",
        f".heading{{fill:{theme.heading};}}",
        "text,tspan{white-space:pre;}",
        "</style>",
        # Full bleed, and no corner radius: LinkedIn masks the corners itself,
        # and a rounded rect here would show through as four dark notches.
        f'<rect width="{banner.width}" height="{banner.height}" fill="{theme.bg}"/>',
    ]

    head_baseline = y0 + banner.headline_font_size
    if box["head_runs"]:
        parts.append(
            f'<text x="{x0}" y="{head_baseline}" fill="{theme.fg}" '
            f'font-size="{banner.headline_font_size}px">'
            f'{_runs_to_tspans(box["head_runs"], classes)}</text>'
        )
    sub_baseline = head_baseline + lh
    if box["sub_runs"]:
        parts.append(
            f'<text x="{x0}" y="{sub_baseline}" fill="{theme.dim}">'
            f'{_runs_to_tspans(box["sub_runs"], classes)}</text>'
        )
    if box["link_runs"]:
        # Right-aligned to the block's edge rather than the canvas's, so it
        # tracks the body columns instead of floating away from them.
        link_x = x0 + box["block_w"] - round(
            visible_length(box["link_runs"]) * cw
        )
        parts.append(
            f'<text x="{link_x}" y="{sub_baseline}" fill="{theme.dim}">'
            f'{_runs_to_tspans(box["link_runs"], classes)}</text>'
        )
    if box["head_h"]:
        # Below the whole header block, not just the headline: measured from
        # the headline it landed on the subhead's baseline and struck it
        # through. Set inside the gap, nearer the header than the body.
        rule_y = y0 + box["head_h"] + round(banner.headline_gap * 0.35)
        parts.append(
            f'<line x1="{x0}" y1="{rule_y}" x2="{x0 + box["block_w"]}" y2="{rule_y}" '
            f'stroke="{theme.rule}" stroke-width="1"/>'
        )

    body_top = y0 + box["head_h"] + (banner.headline_gap if box["head_h"] else 0)
    baseline = body_top + banner.font_size

    x = x0
    for col, col_width in zip(box["columns"], box["col_widths"]):
        parts.append(f'<text x="{x}" y="{baseline}" fill="{theme.fg}">')
        for row, line in enumerate(col):
            y = baseline + row * lh
            parts.append(
                f'<tspan x="{x}" y="{y}">{_runs_to_tspans(line.runs, classes)}</tspan>'
            )
        parts.append("</text>")

        for row, line in enumerate(col):
            if not line.heading:
                continue
            rule_x = round(x + (visible_length(line.runs) + 1) * cw)
            end = round(x + col_width * cw)
            if end <= rule_x:
                continue
            y = baseline + row * lh - round(banner.font_size * 0.3)
            parts.append(
                f'<line x1="{rule_x}" y1="{y}" x2="{end}" y2="{y}" '
                f'stroke="{theme.rule}" stroke-width="1"/>'
            )
        x = round(x + (col_width + banner.column_gutter) * cw)

    parts.append("</svg>")
    return "\n".join(parts) + "\n", box["warnings"]


# LinkedIn takes PNG and JPEG, not SVG, so the banner has to be rasterised
# before it can be uploaded. There is no pure-Python rasteriser in
# requirements.txt and adding cairo to a project that otherwise needs four pure
# wheels is a poor trade, so a headless Chromium does it -- every one of these
# ships the same renderer the SVG was designed against.
CHROMIUM_CANDIDATES = (
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
)


def find_chromium() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "brave-browser"):
        found = shutil.which(name)
        if found:
            return found
    for path in CHROMIUM_CANDIDATES:
        if Path(path).exists():
            return path
    return None


def rasterize(svg: Path, png: Path, banner: BannerConfig) -> None:
    """Screenshot ``svg`` to ``png`` at exactly the banner's dimensions.

    Rendered at ``scale`` times the target and resampled down, because the
    banner is itself downscaled about 2x by LinkedIn and small monospace text
    that has been through two rounds of naive antialiasing goes muddy.
    """
    browser = find_chromium()
    if not browser:
        raise ConfigError(
            "banner.png: no Chromium-based browser found to rasterise with. "
            "Install Chrome, Chromium or Brave, or convert "
            f"{svg} to PNG yourself -- the SVG is already written"
        )
    png.parent.mkdir(parents=True, exist_ok=True)
    scale = max(1, banner.scale)
    subprocess.run(
        [
            browser,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--force-device-scale-factor={scale}",
            f"--window-size={banner.width},{banner.height}",
            f"--screenshot={png}",
            svg.resolve().as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if not png.exists():
        raise ConfigError(f"banner.png: {browser} wrote no file")

    from PIL import Image

    with Image.open(png) as im:
        # Flattened onto the theme background and saved without alpha: LinkedIn
        # composites over white, so a transparent edge pixel would fringe.
        flat = Image.new("RGB", im.size, "#000000")
        flat.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
        if flat.size != (banner.width, banner.height):
            flat = flat.resize((banner.width, banner.height), Image.LANCZOS)
        flat.save(png, "PNG", optimize=True)


def write(banner: BannerConfig, theme: Theme, values: dict[str, str], png: bool = True):
    """Write the banner SVG, and its PNG when a rasteriser is available."""
    svg_text, warnings = render(banner, theme, values)
    out = Path(banner.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg_text, encoding="utf-8")
    written = [out]

    if png and banner.png:
        png_path = Path(banner.png)
        try:
            rasterize(out, png_path, banner)
            written.append(png_path)
        except (ConfigError, subprocess.CalledProcessError) as exc:
            print(f"warning: {exc}", file=sys.stderr)

    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    return written
