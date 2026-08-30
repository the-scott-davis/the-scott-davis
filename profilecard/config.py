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


@dataclass
class Field:
    """One line of the card."""

    label: str | None = None
    value: str = ""
    separator: bool = False
    # Forces the next field into the following column. Ignored in one-column
    # layouts, so leaving one in place costs nothing when the portrait is back on.
    column_break: bool = False
    enabled: bool = True

    @property
    def label_parts(self) -> list[str]:
        """``Languages.Programming`` -> ``['Languages', 'Programming']``."""
        return self.label.split(".") if self.label else []

    @classmethod
    def parse(cls, data: Any, index: int) -> "Field":
        where = f"card.fields[{index}]"
        if data in ("---", "separator"):  # shorthand for a blank spacer line
            return cls(separator=True)
        data = _as_dict(data, where)
        if data.get("separator"):
            return cls(separator=True, enabled=bool(data.get("enabled", True)))
        if data.get("column_break"):
            return cls(column_break=True, enabled=bool(data.get("enabled", True)))
        if "label" not in data:
            raise ConfigError(
                f"{where}: needs one of 'label', 'separator: true', 'column_break: true'"
            )
        return cls(
            label=str(data["label"]),
            value="" if data.get("value") is None else str(data["value"]),
            enabled=bool(data.get("enabled", True)),
        )


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
    path: Path = DEFAULT_CONFIG_PATH

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
            path=path,
        )
