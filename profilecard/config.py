"""Load and validate ``config.yml``.

Everything the card shows is declared in that file.  This module turns it into
plain dataclasses and fails loudly -- with the offending key in the message --
when something is missing or misspelled, so a fork never renders a card that is
silently half-wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .ascii_art import PortraitOptions
from .pixel_art import PixelOptions

DEFAULT_CONFIG_PATH = Path("config.yml")


class ConfigError(ValueError):
    """Raised when config.yml is malformed.  The message names the bad key."""


def _require(data: dict, key: str, where: str) -> Any:
    if key not in data:
        raise ConfigError(f"{where}: missing required key {key!r}")
    return data[key]


def _opt_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _opt_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _as_dict(value: Any, where: str) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ConfigError(f"{where}: expected a mapping, got {type(value).__name__}")
    return value


DEFAULT_AFFILIATIONS = ["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"]
DEFAULT_STAR_AFFILIATIONS = ["OWNER"]


@dataclass
class GitHubConfig:
    username: str
    affiliations: list[str] = field(default_factory=lambda: list(DEFAULT_AFFILIATIONS))
    star_affiliations: list[str] = field(default_factory=lambda: list(DEFAULT_STAR_AFFILIATIONS))
    exclude_repos: list[str] = field(default_factory=list)
    only_my_commits: bool = True
    # Line counting walks every commit of every repository. On a large account
    # that is minutes and thousands of API calls, against a couple of seconds
    # for everything else, so it is opt-in.
    count_lines: bool = False

    @classmethod
    def parse(cls, data: dict) -> "GitHubConfig":
        data = _as_dict(data, "github")
        username = _require(data, "username", "github")
        if not username or username == "REPLACE_ME":
            raise ConfigError(
                "github.username is still the placeholder -- set it to your GitHub login"
            )
        return cls(
            username=str(username),
            affiliations=list(data.get("affiliations", DEFAULT_AFFILIATIONS)),
            star_affiliations=list(data.get("star_affiliations", DEFAULT_STAR_AFFILIATIONS)),
            exclude_repos=list(data.get("exclude_repos", []) or []),
            only_my_commits=bool(data.get("only_my_commits", True)),
            count_lines=bool(data.get("count_lines", False)),
        )


DEFAULT_EXCLUDE_LANGUAGES = ["HTML", "CSS", "SCSS", "Less", "Dockerfile", "Shell"]


@dataclass
class StackConfig:
    """How to decide what someone actually builds with.

    GitHub's language stats measure bytes and have no sense of time, so one large
    legacy service can outrank every recent project. ``since_years`` fixes the
    time blindness; ``exclude_languages`` fixes markup and dead stacks crowding
    out real work.
    """

    since_years: float | None = 1.0
    exclude_languages: list[str] = field(
        default_factory=lambda: list(DEFAULT_EXCLUDE_LANGUAGES)
    )
    exclude_tech: list[str] = field(default_factory=list)
    limit: int = 8
    # Repositories to sample commit timestamps from, for the hour histogram.
    sample_repos: int = 6
    # Commit timestamps arrive in UTC and have to be shifted to local time.
    # An IANA name is preferred -- it gets daylight saving right across a whole
    # year of commits. The fixed offset is the fallback for interpreters older
    # than 3.9, where zoneinfo is unavailable.
    timezone: str | None = None
    timezone_offset: int = 0

    @classmethod
    def parse(cls, data: dict) -> "StackConfig":
        data = _as_dict(data, "stack")
        known = {
            "since_years", "exclude_languages", "exclude_tech", "limit",
            "sample_repos", "timezone", "timezone_offset",
        }
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"stack: unknown key(s) {sorted(unknown)}")
        since = data.get("since_years", cls.since_years)
        return cls(
            since_years=None if since in (None, 0) else float(since),
            exclude_languages=list(
                data.get("exclude_languages", DEFAULT_EXCLUDE_LANGUAGES) or []
            ),
            exclude_tech=list(data.get("exclude_tech", []) or []),
            limit=int(data.get("limit", cls.limit)),
            sample_repos=int(data.get("sample_repos", cls.sample_repos)),
            timezone=data.get("timezone") or None,
            timezone_offset=int(data.get("timezone_offset", cls.timezone_offset)),
        )


HEATMAP_SOURCES = {"contributions"}


@dataclass
class Field:
    """One line of the card."""

    label: str | None = None
    value: str = ""
    separator: bool = False
    # A section title. Implies the break a `separator` would have made, so the
    # two are not written together.
    heading: str | None = None
    # A block of contribution squares rather than a row of text. Names the data
    # it draws; only "contributions" exists so far.
    heatmap: str | None = None
    # Forces the next field into the following column. Ignored in one-column
    # layouts, so leaving one in place costs nothing when the portrait is back on.
    column_break: bool = False
    enabled: bool = True

    @property
    def label_parts(self) -> list[str]:
        """``Languages.Programming`` -> ``['Languages', 'Programming']``."""
        return self.label.split(".") if self.label else []

    @classmethod
    def parse(cls, data: Any, index: int, prefix: str = "card") -> "Field":
        where = f"{prefix}.fields[{index}]"
        if data in ("---", "separator"):  # shorthand for a blank spacer line
            return cls(separator=True)
        data = _as_dict(data, where)
        if data.get("separator"):
            return cls(separator=True, enabled=bool(data.get("enabled", True)))
        if data.get("column_break"):
            return cls(column_break=True, enabled=bool(data.get("enabled", True)))
        if data.get("heading") is not None:
            return cls(
                heading=str(data["heading"]), enabled=bool(data.get("enabled", True))
            )
        if data.get("heatmap") is not None:
            source = str(data["heatmap"])
            if source not in HEATMAP_SOURCES:
                raise ConfigError(
                    f"{where}.heatmap: expected one of {sorted(HEATMAP_SOURCES)}, "
                    f"got {source!r}"
                )
            return cls(heatmap=source, enabled=bool(data.get("enabled", True)))
        if "label" not in data:
            raise ConfigError(
                f"{where}: needs one of 'label', 'heading', 'heatmap', "
                "'separator: true', 'column_break: true'"
            )
        return cls(
            label=str(data["label"]),
            value="" if data.get("value") is None else str(data["value"]),
            enabled=bool(data.get("enabled", True)),
        )


def _blend(a: str, b: str, t: float) -> str:
    """``a`` toward ``b`` by ``t``, in plain sRGB. Good enough for five shades."""
    def parts(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    return "#" + "".join(
        f"{round(x + (y - x) * t):02x}" for x, y in zip(parts(a), parts(b))
    )


def _heat_ramp(data: dict, where: str, bg: str, accent: str) -> list[str]:
    """Five shades for the contribution grid, quietest first."""
    ramp = data.get("heat")
    if ramp is None:
        # The empty cell lifts off the background rather than sitting on the
        # accent, or a blank year reads as a hole in the card.
        return [_blend(bg, accent, t) for t in (0.10, 0.32, 0.55, 0.78, 1.0)]
    if not isinstance(ramp, list) or len(ramp) != 5:
        raise ConfigError(f"{where}.heat: expected a list of 5 colours, quietest first")
    return [str(c) for c in ramp]


@dataclass
class Theme:
    name: str
    output: str
    # Empty when the theme draws no portrait. Only `card.show_portrait: true`
    # makes it mandatory, and render.py is where that is enforced -- a theme
    # cannot see the card config from here.
    portrait: str
    bg: str
    fg: str
    key: str
    value: str
    dim: str
    add: str
    delete: str
    rule: str
    heading: str
    # Five shades for the contribution grid, quietest first. Defaults to a blend
    # from the background up to `key`, so a fork gets a card-coloured grid
    # without configuring one.
    heat: list[str] = field(default_factory=list)

    @classmethod
    def parse(cls, name: str, data: dict) -> "Theme":
        where = f"themes.{name}"
        data = _as_dict(data, where)
        fg = str(_require(data, "fg", where))
        dim = str(data.get("dim", fg))
        return cls(
            name=name,
            output=str(_require(data, "output", where)),
            portrait=str(data.get("portrait") or ""),
            bg=str(_require(data, "bg", where)),
            fg=fg,
            key=str(data.get("key", fg)),
            value=str(data.get("value", fg)),
            dim=dim,
            add=str(data.get("add", fg)),
            delete=str(data.get("delete", fg)),
            rule=str(data.get("rule", dim)),
            heading=str(data.get("heading", fg)),
            heat=_heat_ramp(data, where, str(_require(data, "bg", where)),
                            str(data.get("key", fg))),
        )


@dataclass
class CardConfig:
    title: str = "{username}@github"
    font_size: int = 16
    line_height: int = 20
    char_width: float = 9.6
    padding: int = 18
    corner_radius: int = 14
    gutter: int = 4  # blank columns between the portrait and the field list
    column_gutter: int = 4  # blank columns between two field columns
    # Extra pixels between the title and the first row. The rule under the title
    # sits in the middle of it, so the gap is what keeps that rule off both.
    title_gap: int = 10
    heat_cell: int = 7  # side of one contribution square
    heat_gap: int = 2  # space between squares
    min_dots: int = 2
    # The portrait is optional. Turning it off frees the whole width for text,
    # which is why `columns` then defaults to 2 -- a single tall column of rows
    # against a wide README is mostly empty space.
    show_portrait: bool = True
    columns: int | None = None  # None -> 1 with a portrait, 2 without
    pixel_size: int = 7  # SVG pixels per art pixel, for a pixel-art portrait
    portrait_radius: int = 6  # rounded corners on a pixel-art portrait
    # An ASCII portrait is texture, not text, so it does not have to be set at a
    # readable size. Shrinking it buys cells, and cells are detail. These fall
    # back to the field-text metrics when unset.
    portrait_font_size: int | None = None
    portrait_line_height: int | None = None
    portrait_char_width: float | None = None

    @property
    def column_count(self) -> int:
        return self.columns if self.columns is not None else (1 if self.show_portrait else 2)

    @property
    def art_font_size(self) -> int:
        return self.portrait_font_size or self.font_size

    @property
    def art_line_height(self) -> int:
        if self.portrait_line_height is not None:
            return self.portrait_line_height
        if self.portrait_font_size is not None:
            # Keep the field text's leading ratio, so setting the portrait font
            # size alone gives sane line spacing instead of huge gaps.
            return max(1, round(self.portrait_font_size * self.line_height / self.font_size))
        return self.line_height

    @property
    def art_char_width(self) -> float:
        if self.portrait_char_width is not None:
            return self.portrait_char_width
        if self.portrait_font_size is not None:
            return round(self.portrait_font_size * 0.6, 2)
        return self.char_width
    fields: list[Field] = field(default_factory=list)

    @classmethod
    def parse(cls, data: dict) -> "CardConfig":
        data = _as_dict(data, "card")
        raw_fields = data.get("fields") or []
        if not isinstance(raw_fields, list):
            raise ConfigError("card.fields: expected a list")
        fields = [Field.parse(item, i) for i, item in enumerate(raw_fields)]
        columns = _opt_int(data.get("columns"))
        if columns is not None and columns < 1:
            raise ConfigError(f"card.columns: expected 1 or more, got {columns}")
        return cls(
            title=str(data.get("title", cls.title)),
            font_size=int(data.get("font_size", cls.font_size)),
            line_height=int(data.get("line_height", cls.line_height)),
            char_width=float(data.get("char_width", cls.char_width)),
            padding=int(data.get("padding", cls.padding)),
            corner_radius=int(data.get("corner_radius", cls.corner_radius)),
            gutter=int(data.get("gutter", cls.gutter)),
            column_gutter=int(data.get("column_gutter", cls.column_gutter)),
            title_gap=int(data.get("title_gap", cls.title_gap)),
            heat_cell=int(data.get("heat_cell", cls.heat_cell)),
            heat_gap=int(data.get("heat_gap", cls.heat_gap)),
            min_dots=int(data.get("min_dots", cls.min_dots)),
            show_portrait=bool(data.get("show_portrait", cls.show_portrait)),
            columns=columns,
            pixel_size=int(data.get("pixel_size", cls.pixel_size)),
            portrait_radius=int(data.get("portrait_radius", cls.portrait_radius)),
            portrait_font_size=_opt_int(data.get("portrait_font_size")),
            portrait_line_height=_opt_int(data.get("portrait_line_height")),
            portrait_char_width=_opt_float(data.get("portrait_char_width")),
            fields=[f for f in fields if f.enabled],
        )



@dataclass
class BannerConfig:
    """A fixed-size social banner -- a LinkedIn cover -- built from the same stats.

    The card sizes itself to its content.  This cannot: the canvas is fixed, so
    the content is measured against it and overflow is an error.  See
    :mod:`profilecard.banner` for what the defaults are protecting against.
    """

    output: str = "dist/linkedin_banner.svg"
    png: str = "dist/linkedin_banner.png"
    # Which entry under `themes:` supplies the palette. A banner is one baked
    # image, so unlike the README it cannot follow the reader's colour scheme.
    theme: str = "dark"
    width: int = 1584
    height: int = 396
    # Supersampling for the PNG. LinkedIn downscales the image again, and text
    # that has been antialiased twice at 1x goes muddy.
    scale: int = 2
    # The app crops to roughly the centre 60% of the width. Content wider than
    # this is reported, not refused -- it is a warning about phones, not a
    # layout failure.
    safe_width: int = 950
    headline: str = ""
    # A quieter second line under the headline, set at the body size. The
    # header is where anything that would otherwise sit in the bottom-left
    # corner has to go, because the profile photo covers that corner.
    subhead: str = ""
    link: str = ""
    headline_font_size: int = 28
    headline_line_height: int | None = None
    headline_char_width: float | None = None
    headline_gap: int = 18
    # Larger than the card's 16px on purpose: LinkedIn shows the banner at
    # roughly half these pixel dimensions, so the card's size arrives at 7px.
    font_size: int = 22
    line_height: int = 28
    char_width: float | None = None
    columns: int = 2
    # Caps a column at this many characters, wrapping long values onto
    # continuation rows. Height is the resource this canvas has spare and width
    # is the one it does not, so wrapping a list rather than letting it run is
    # what buys the type size back. None leaves values on one row.
    wrap_cols: int | None = None
    column_gutter: int = 4
    min_dots: int = 2
    # Nudges the block off centre, to buy clearance from the profile photo in
    # the bottom-left corner at the cost of symmetry under the mobile crop.
    offset_x: int = 0
    # The vertical equivalent. A block is centred on the canvas, so an
    # asymmetric one -- a short left column against a long right one -- sits
    # lower than its left column can afford, because the photo's top edge does
    # not move when the block shrinks. Negative lifts it.
    offset_y: int = 0
    fields: list[Field] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.char_width is None:
            self.char_width = round(self.font_size * 0.6, 2)
        if self.headline_char_width is None:
            self.headline_char_width = round(self.headline_font_size * 0.6, 2)
        if self.headline_line_height is None:
            self.headline_line_height = round(self.headline_font_size * 1.25)

    def as_card(self) -> "CardConfig":
        """The banner's fields as a card, so the column machinery can be reused.

        The title is blanked deliberately: the banner sets its headline at a
        larger size and measures it separately, and a title left in here would
        silently widen the body columns to match it.
        """
        return CardConfig(
            title="",
            font_size=self.font_size,
            line_height=self.line_height,
            char_width=self.char_width,
            columns=self.columns,
            column_gutter=self.column_gutter,
            min_dots=self.min_dots,
            show_portrait=False,
            fields=self.fields,
        )

    @classmethod
    def parse(cls, data: Any) -> "BannerConfig | None":
        if not data:
            return None
        data = _as_dict(data, "banner")
        # Off is the same as absent: nothing is rendered and nothing is written,
        # so a banner still being designed leaves no artifact in the repository
        # for the nightly job to publish. The rest of the section is still
        # parsed and validated first, so a typo in a switched-off banner is
        # caught now rather than the day it is switched back on.
        raw_fields = data.get("fields") or []
        if not isinstance(raw_fields, list):
            raise ConfigError("banner.fields: expected a list")
        fields = [Field.parse(item, i, "banner") for i, item in enumerate(raw_fields)]
        for i, f in enumerate(fields):
            if f.heatmap:
                raise ConfigError(
                    f"banner.fields[{i}]: a heatmap does not fit a fixed canvas "
                    "-- it is several rows tall and would push the block off it"
                )
        known = {
            "output", "png", "theme", "width", "height", "scale", "safe_width",
            "headline", "subhead", "link", "headline_font_size", "headline_line_height",
            "headline_char_width", "headline_gap", "font_size", "line_height",
            "char_width", "columns", "wrap_cols", "column_gutter", "min_dots", "offset_x",
            "offset_y", "enabled", "fields",
        }
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"banner: unknown key(s) {sorted(unknown)}")
        columns = int(data.get("columns", cls.columns))
        if columns < 1:
            raise ConfigError(f"banner.columns: expected 1 or more, got {columns}")
        if not data.get("enabled", True):
            return None
        return cls(
            output=str(data.get("output", cls.output)),
            png=str(data.get("png", cls.png) or ""),
            theme=str(data.get("theme", cls.theme)),
            width=int(data.get("width", cls.width)),
            height=int(data.get("height", cls.height)),
            scale=int(data.get("scale", cls.scale)),
            safe_width=int(data.get("safe_width", cls.safe_width)),
            headline=str(data.get("headline", cls.headline)),
            subhead=str(data.get("subhead", cls.subhead)),
            link=str(data.get("link", cls.link)),
            headline_font_size=int(data.get("headline_font_size", cls.headline_font_size)),
            headline_line_height=_opt_int(data.get("headline_line_height")),
            headline_char_width=_opt_float(data.get("headline_char_width")),
            headline_gap=int(data.get("headline_gap", cls.headline_gap)),
            font_size=int(data.get("font_size", cls.font_size)),
            line_height=int(data.get("line_height", cls.line_height)),
            char_width=_opt_float(data.get("char_width")),
            columns=columns,
            wrap_cols=_opt_int(data.get("wrap_cols")),
            column_gutter=int(data.get("column_gutter", cls.column_gutter)),
            min_dots=int(data.get("min_dots", cls.min_dots)),
            offset_x=int(data.get("offset_x", cls.offset_x)),
            offset_y=int(data.get("offset_y", cls.offset_y)),
            fields=[f for f in fields if f.enabled],
        )


# Two rendering modes, each with its own option set.  `pixel` produces a small
# colour PNG; `ascii` produces a block of characters.  Pixels carry enough
# information for a face to be recognisable, which is why they are the default.
MODES = ("pixel", "ascii")

ASCII_OPTION_KEYS = {
    "width", "height", "cell_aspect", "ramp", "invert", "black_point",
    "white_point", "gamma", "autocontrast", "sharpen", "vignette",
    "vignette_power", "floor", "trim", "ink_floor", "crop",
}
PIXEL_OPTION_KEYS = {
    "width", "height", "crop", "palette", "dither", "saturation", "contrast",
    "brightness", "sharpen",
}


def _portrait_options(data: dict, where: str, mode: str, base=None):
    """Build options from ``data``, layered over ``base`` when given."""
    keys = PIXEL_OPTION_KEYS if mode == "pixel" else ASCII_OPTION_KEYS
    cls = PixelOptions if mode == "pixel" else PortraitOptions

    unknown = set(data) - keys - {"source", "outputs", "path", "mode"}
    if unknown:
        other = ASCII_OPTION_KEYS if mode == "pixel" else PIXEL_OPTION_KEYS
        hint = ""
        if unknown & other:
            hint = f" -- {sorted(unknown & other)} belong to the other mode"
        raise ConfigError(f"{where}: unknown key(s) {sorted(unknown)} for mode {mode!r}{hint}")

    values = dict(vars(base)) if base else {}
    for key in keys & set(data):
        value = data[key]
        if key == "crop" and value is not None:
            if len(value) != 4:
                raise ConfigError(f"{where}.crop: expected [left, top, right, bottom]")
            value = tuple(float(v) for v in value)
        values[key] = value
    return cls(**values)


@dataclass
class PortraitOutput:
    name: str
    path: str
    options: object  # PixelOptions or PortraitOptions, matching the mode


@dataclass
class PortraitConfig:
    source: str
    mode: str
    outputs: list[PortraitOutput]
    options: object

    @classmethod
    def parse(cls, data: dict) -> "PortraitConfig | None":
        if not data:
            return None
        data = _as_dict(data, "portrait")
        source = _require(data, "source", "portrait")

        mode = str(data.get("mode", "pixel"))
        if mode not in MODES:
            raise ConfigError(f"portrait.mode: expected one of {list(MODES)}, got {mode!r}")

        raw_outputs = _as_dict(data.get("outputs"), "portrait.outputs")
        if not raw_outputs:
            raise ConfigError("portrait.outputs: needs at least one output")

        base = _portrait_options(data, "portrait", mode)

        outputs = []
        for name, spec in raw_outputs.items():
            where = f"portrait.outputs.{name}"
            # A bare string is shorthand for {path: <string>}.
            if isinstance(spec, str):
                spec = {"path": spec}
            spec = _as_dict(spec, where)
            path = _require(spec, "path", where)
            outputs.append(
                PortraitOutput(
                    name=name,
                    path=str(path),
                    options=_portrait_options(spec, where, mode, base),
                )
            )
        return cls(source=str(source), mode=mode, outputs=outputs, options=base)


@dataclass
class Config:
    github: GitHubConfig
    card: CardConfig
    themes: list[Theme]
    vars: dict[str, Any] = field(default_factory=dict)
    stack: StackConfig = field(default_factory=StackConfig)
    portrait: PortraitConfig | None = None
    banner: BannerConfig | None = None
    path: Path = DEFAULT_CONFIG_PATH

    def banner_theme(self) -> Theme:
        """The theme the banner names.  A banner is one image, so it picks one."""
        if not self.banner:
            raise ConfigError("banner: no banner section in config.yml")
        for theme in self.themes:
            if theme.name == self.banner.theme:
                return theme
        known = ", ".join(t.name for t in self.themes)
        raise ConfigError(
            f"banner.theme: no theme named {self.banner.theme!r} (defined: {known})"
        )

    @classmethod
    def load(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "Config":
        path = Path(path)
        if not path.exists():
            raise ConfigError(
                f"{path} not found -- run from the repository root, "
                "or pass --config with a path to it"
            )
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ConfigError(f"{path}: top level must be a mapping")

        themes_raw = _as_dict(raw.get("themes"), "themes")
        if not themes_raw:
            raise ConfigError("themes: define at least one theme")

        return cls(
            github=GitHubConfig.parse(raw.get("github")),
            card=CardConfig.parse(raw.get("card")),
            themes=[Theme.parse(n, d) for n, d in themes_raw.items()],
            vars=_as_dict(raw.get("vars"), "vars"),
            stack=StackConfig.parse(raw.get("stack")),
            portrait=PortraitConfig.parse(raw.get("portrait")),
            banner=BannerConfig.parse(raw.get("banner")),
            path=path,
        )
