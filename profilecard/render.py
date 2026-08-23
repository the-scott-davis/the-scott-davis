"""Generate the card SVG from a :class:`~profilecard.config.Config` and a stats dict.

The upstream project this is modelled on shipped two hand-written SVGs and used
XML surgery to poke numbers into fixed ``id`` attributes -- which meant adding a
row was a manual re-layout of every ``y`` coordinate in both files.  Here the
SVG is generated: column alignment, dot leaders, and the canvas size are all
computed from the content, so the config file is the only thing you edit.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import CardConfig, Config, ConfigError, Field, Theme
from .pixel_art import boxes_to_paths, load_boxes

# Portraits are identified by extension rather than by a config flag, so a theme
# is self-describing: point it at a .png and you get pixel art, at a .txt and you
# get characters.
PIXEL_SUFFIXES = {".png", ".gif", ".bmp", ".webp"}

# <key>..</key>, <dim>..</dim>, and friends.  Anything else stays literal text.
STYLE_TAGS = ("key", "value", "dim", "add", "del")
_TAG_RE = re.compile(r"<(/?)(" + "|".join(STYLE_TAGS) + r")>")
_NAME_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]*")

_XML_ESCAPES = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}


def xml_escape(text: str) -> str:
    return "".join(_XML_ESCAPES.get(c, c) for c in text)


@dataclass
class Run:
    """A contiguous piece of text sharing one style class."""

    text: str
    style: str | None = None  # None -> inherit the parent text colour


def substitute(template: str, values: dict[str, str], where: str) -> str:
    """Expand ``{placeholder}`` against ``values``; ``{{`` / ``}}`` stay literal.

    Scanned left to right rather than pattern-matched: ``{{{name}}}`` has to come
    out as ``{`` + the value + ``}``, and a regex cannot tell that apart from a
    doubled brace wrapping a literal name without backtracking into the wrong
    answer.

    Unknown names raise instead of silently rendering ``{typo}`` onto the card.
    """
    out: list[str] = []
    i, n = 0, len(template)
    while i < n:
        char = template[i]
        if char == "{":
            if template.startswith("{{", i):
                out.append("{")
                i += 2
                continue
            match = _NAME_RE.match(template, i + 1)
            if not match or not template.startswith("}", match.end()):
                raise ConfigError(
                    f"{where}: unmatched '{{' at position {i} in {template!r} "
                    "(use '{{' for a literal brace)"
                )
            name = match.group(0)
            if name not in values:
                known = ", ".join(sorted(values))
                raise ConfigError(f"{where}: unknown placeholder {{{name}}} (available: {known})")
            out.append(str(values[name]))
            i = match.end() + 1
        elif char == "}":
            out.append("}")
            i += 2 if template.startswith("}}", i) else 1
        else:
            out.append(char)
            i += 1
    return "".join(out)


def parse_markup(text: str) -> list[Run]:
    """Split ``a <add>b</add> c`` into styled runs.  Tags may not nest."""
    runs: list[Run] = []
    style: str | None = None
    pos = 0
    for match in _TAG_RE.finditer(text):
        if match.start() > pos:
            runs.append(Run(text[pos : match.start()], style))
        closing, tag = match.group(1), match.group(2)
        if closing:
            if style != tag:
                raise ConfigError(f"markup: </{tag}> without a matching <{tag}> in {text!r}")
            style = None
        else:
            if style is not None:
                raise ConfigError(f"markup: <{tag}> nested inside <{style}> in {text!r}")
            style = tag
        pos = match.end()
    if style is not None:
        raise ConfigError(f"markup: unclosed <{style}> in {text!r}")
    if pos < len(text):
        runs.append(Run(text[pos:], style))
    return [r for r in runs if r.text]


def visible_length(runs: list[Run]) -> int:
    return sum(len(r.text) for r in runs)


@dataclass
class Line:
    """One rendered row of the right-hand column."""

    runs: list[Run]


def _leader(width: int) -> str:
    """A dot leader ``width`` characters wide, padded away from the text."""
    if width <= 0:
        return ""
    if width == 1:
        return " "
    if width == 2:
        return "  "
    return " " + "." * (width - 2) + " "


def build_lines(card: CardConfig, values: dict[str, str]) -> list[Line]:
    """Expand every field, then align all values into a single column."""
    title_runs = parse_markup(substitute(card.title, values, "card.title"))

    # Pass 1: expand labels and values, and measure the label column.
    expanded: list[tuple[Field, list[Run], list[Run]]] = []
    for i, f in enumerate(card.fields):
        if f.separator:
            expanded.append((f, [], []))
            continue
        where = f"card.fields[{i}] ({f.label})"
        label_runs: list[Run] = []
        for j, part in enumerate(f.label_parts):
            if j:
                label_runs.append(Run(".", "dim"))
            label_runs.append(Run(substitute(part, values, where), "key"))
        label_runs.append(Run(":", None))
        value_runs = parse_markup(substitute(f.value, values, where))
        expanded.append((f, label_runs, value_runs))

    gutter = ". "  # neofetch-style left rail
    label_width = max(
        (visible_length(lr) for _, lr, _ in expanded if lr),
        default=0,
    )
    value_col = label_width + max(2, card.min_dots + 2)

    lines = [Line(title_runs)]
    for f, label_runs, value_runs in expanded:
        if f.separator:
            lines.append(Line([Run(gutter.rstrip(), "dim")]))
            continue
        pad = value_col - visible_length(label_runs)
        runs = [Run(gutter, "dim"), *label_runs, Run(_leader(pad), "dim")]
        runs.extend(value_runs or [Run("", None)])
        lines.append(Line(runs))
    return lines


def _runs_to_tspans(runs: list[Run], theme_classes: dict[str, str]) -> str:
    out = []
    for run in runs:
        text = xml_escape(run.text)
        cls = theme_classes.get(run.style or "", None)
        out.append(f'<tspan class="{cls}">{text}</tspan>' if cls else text)
    return "".join(out)


def _pixel_portrait(path: Path, card: CardConfig, pad: int) -> tuple[list[str], int, int]:
    """SVG for a pixel-art portrait, plus the box it occupies in card pixels.

    Drawn inside a ``scale()`` so every coordinate stays a small integer, and
    with ``crispEdges`` so neighbouring pixels butt up against each other
    instead of showing antialiased seams.
    """
    art_w, art_h, boxes = load_boxes(path)
    size = card.pixel_size
    width, height = art_w * size, art_h * size

    parts = []
    clip = ""
    if card.portrait_radius > 0:
        clip = f"portrait-{art_w}x{art_h}"
        parts.append(
            f'<clipPath id="{clip}"><rect x="{pad}" y="{pad}" width="{width}" '
            f'height="{height}" rx="{card.portrait_radius}"/></clipPath>'
        )
    clip_attr = f' clip-path="url(#{clip})"' if clip else ""
    parts.append(
        f"<g{clip_attr} "
        f'transform="translate({pad} {pad}) scale({size})" shape-rendering="crispEdges">'
    )
    for color, data in boxes_to_paths(boxes):
        parts.append(f'<path fill="{color}" d="{data}"/>')
    parts.append("</g>")
    return parts, width, height


def _ascii_portrait(
    path: Path, card: CardConfig, pad: int, fill: str
) -> tuple[list[str], int, int]:
    """SVG for a character portrait, plus the box it occupies in card pixels.

    Set at its own font size rather than the field text's: a portrait is texture,
    not something anyone reads, so shrinking the type buys cells and cells are
    the only source of detail an ASCII portrait has.
    """
    rows = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    cols = max((len(r) for r in rows), default=0)
    fs, lh, cw = card.art_font_size, card.art_line_height, card.art_char_width
    baseline = pad + fs

    parts = [
        f'<text x="{pad}" y="{baseline}" fill="{fill}" font-size="{fs}px" aria-hidden="true">'
    ]
    for i, row in enumerate(rows):
        parts.append(f'<tspan x="{pad}" y="{baseline + i * lh}">{xml_escape(row)}</tspan>')
    parts.append("</text>")
    return parts, round(cols * cw), len(rows) * lh


def render_theme(cfg: Config, theme: Theme, values: dict[str, str]) -> str:
    """Render one complete SVG document."""
    card = cfg.card
    portrait_path = Path(theme.portrait)
    if not portrait_path.exists():
        raise ConfigError(
            f"themes.{theme.name}.portrait: {portrait_path} not found "
            "-- run `python -m profilecard.portrait` first"
        )

    lines = build_lines(card, values)
    text_cols = max((visible_length(l.runs) for l in lines), default=0)

    cw, lh, pad = card.char_width, card.line_height, card.padding
    baseline = pad + lh - 5  # first baseline, nudged for cap height

    if portrait_path.suffix.lower() in PIXEL_SUFFIXES:
        portrait_parts, portrait_w, portrait_h = _pixel_portrait(portrait_path, card, pad)
    else:
        portrait_parts, portrait_w, portrait_h = _ascii_portrait(
            portrait_path, card, pad, theme.fg
        )

    # One spare column: monospace advances differ by a hair across platforms and
    # a clipped last character is far worse than a sliver of extra padding.
    text_x = round(pad + portrait_w + card.gutter * cw)
    width = round(text_x + (text_cols + 1) * cw + pad)
    height = pad * 2 + max(portrait_h, len(lines) * lh)

    classes = {t: t for t in STYLE_TAGS}

    parts = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" '
        f'width="{width}px" height="{height}px" viewBox="0 0 {width} {height}" '
        f'font-family="ConsolasFallback,\'DejaVu Sans Mono\',Menlo,Consolas,monospace" '
        f'font-size="{card.font_size}px">',
        f"<title>{xml_escape(values.get('name', values['username']))}"
        f" — GitHub profile card</title>",
        "<style>",
        "@font-face{src:local('Consolas');font-family:'ConsolasFallback';"
        "font-display:swap;size-adjust:109%;}",
        f".key{{fill:{theme.key};}}",
        f".value{{fill:{theme.value};}}",
        f".dim{{fill:{theme.dim};}}",
        f".add{{fill:{theme.add};}}",
        f".del{{fill:{theme.delete};}}",
        "text,tspan{white-space:pre;}",
        "</style>",
        f'<rect width="{width}" height="{height}" fill="{theme.bg}" '
        f'rx="{card.corner_radius}"/>',
    ]

    # Portrait column.
    parts.extend(portrait_parts)

    # Field column.
    parts.append(f'<text x="{text_x}" y="{baseline}" fill="{theme.fg}">')
    for i, line in enumerate(lines):
        y = baseline + i * lh
        parts.append(
            f'<tspan x="{text_x}" y="{y}">{_runs_to_tspans(line.runs, classes)}</tspan>'
        )
    parts.append("</text>")

    # Rule under the title, sized to the field column.
    rule_y = baseline + 6
    parts.append(
        f'<line x1="{text_x}" y1="{rule_y}" x2="{round(text_x + text_cols * cw)}" '
        f'y2="{rule_y}" stroke="{theme.rule}" stroke-width="1"/>'
    )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_all(cfg: Config, values: dict[str, str]) -> list[Path]:
    written = []
    for theme in cfg.themes:
        svg = render_theme(cfg, theme, values)
        out = Path(theme.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
        written.append(out)
    return written
