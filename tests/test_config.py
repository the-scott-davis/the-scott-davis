"""Config parsing should fail loudly and point at the offending key."""

import textwrap

import pytest

from profilecard.config import Config, ConfigError

MINIMAL = """
github:
  username: octocat
themes:
  dark:
    output: dist/dark.svg
    portrait: assets/portrait.txt
    bg: "#000"
    fg: "#fff"
card:
  fields:
    - label: OS
      value: Linux
"""


def write(tmp_path, text):
    path = tmp_path / "config.yml"
    path.write_text(textwrap.dedent(text))
    return path


def test_minimal_config_loads(tmp_path):
    cfg = Config.load(write(tmp_path, MINIMAL))
    assert cfg.github.username == "octocat"
    assert [t.name for t in cfg.themes] == ["dark"]
    assert len(cfg.card.fields) == 1


def test_missing_file_says_what_to_do(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        Config.load(tmp_path / "nope.yml")


def test_placeholder_username_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="placeholder"):
        Config.load(write(tmp_path, MINIMAL.replace("octocat", "REPLACE_ME")))


def test_no_themes_is_an_error(tmp_path):
    bad = MINIMAL.split("themes:")[0] + "card:\n  fields: []\n"
    with pytest.raises(ConfigError, match="themes"):
        Config.load(write(tmp_path, bad))


def test_field_without_label_or_separator_names_its_index(tmp_path):
    bad = MINIMAL.replace("    - label: OS\n      value: Linux", "    - value: Linux")
    with pytest.raises(ConfigError, match=r"card\.fields\[0\]"):
        Config.load(write(tmp_path, bad))


def test_disabled_fields_are_dropped(tmp_path):
    extra = MINIMAL + """    - label: Discord
      value: handle
      enabled: false
"""
    assert len(Config.load(write(tmp_path, extra)).card.fields) == 1


def test_separator_shorthand(tmp_path):
    cfg = Config.load(write(tmp_path, MINIMAL + '    - "---"\n'))
    assert cfg.card.fields[-1].separator


def test_dotted_label_splits(tmp_path):
    cfg = Config.load(write(tmp_path, MINIMAL.replace("label: OS", "label: A.B.C")))
    assert cfg.card.fields[0].label_parts == ["A", "B", "C"]


def test_theme_colours_fall_back_to_fg(tmp_path):
    theme = Config.load(write(tmp_path, MINIMAL)).themes[0]
    assert theme.key == theme.value == "#fff"


def test_portrait_output_inherits_then_overrides(tmp_path):
    cfg = Config.load(write(tmp_path, MINIMAL + """
portrait:
  source: assets/photo.jpg
  mode: ascii
  width: 50
  floor: 0.1
  outputs:
    normal:
      path: a.txt
    inverted:
      path: b.txt
      invert: true
      floor: 0.4
"""))
    normal, inverted = cfg.portrait.outputs
    assert (normal.options.width, normal.options.floor, normal.options.invert) == (50, 0.1, False)
    # Inherits width, overrides the rest.
    assert (inverted.options.width, inverted.options.floor, inverted.options.invert) == (50, 0.4, True)


def test_pixel_is_the_default_mode(tmp_path):
    cfg = Config.load(write(tmp_path, MINIMAL + """
portrait:
  source: a.jpg
  width: 64
  palette: 24
  outputs:
    main: p.png
"""))
    assert cfg.portrait.mode == "pixel"
    assert (cfg.portrait.outputs[0].options.width, cfg.portrait.outputs[0].options.palette) == (64, 24)


def test_option_from_the_wrong_mode_says_so(tmp_path):
    # `floor` is an ascii-mode knob; using it under pixel mode is a typo worth catching.
    with pytest.raises(ConfigError, match="belong to the other mode"):
        Config.load(write(tmp_path, MINIMAL + """
portrait:
  source: a.jpg
  mode: pixel
  floor: 0.2
  outputs:
    main: p.png
"""))


def test_bad_mode_lists_the_valid_ones(tmp_path):
    with pytest.raises(ConfigError, match="pixel"):
        Config.load(write(tmp_path, MINIMAL + """
portrait:
  source: a.jpg
  mode: watercolour
  outputs:
    main: p.png
"""))


def test_unknown_portrait_key_is_an_error(tmp_path):
    with pytest.raises(ConfigError, match="unknown key"):
        Config.load(write(tmp_path, MINIMAL + """
portrait:
  source: a.jpg
  paletet: 32
  outputs:
    main: p.png
"""))


def test_bare_string_output_is_shorthand_for_path(tmp_path):
    cfg = Config.load(write(tmp_path, MINIMAL + """
portrait:
  source: a.jpg
  outputs:
    main: out.png
"""))
    assert cfg.portrait.outputs[0].path == "out.png"


class TestPortraitMetrics:
    """The portrait is set at its own size; the fallbacks have to be sane."""

    def _card(self, tmp_path, extra=""):
        return Config.load(write(tmp_path, MINIMAL.replace(
            "card:\n  fields:", "card:\n" + extra + "  fields:"))).card

    def test_defaults_to_the_field_text_metrics(self, tmp_path):
        card = self._card(tmp_path)
        assert (card.art_font_size, card.art_line_height, card.art_char_width) == (
            card.font_size, card.line_height, card.char_width
        )

    def test_font_size_alone_scales_the_leading(self, tmp_path):
        # 16/20 text -> a 10px portrait should get 12px leading, not 20.
        card = self._card(tmp_path, "  portrait_font_size: 10\n")
        assert card.art_font_size == 10
        assert card.art_line_height == 12
        assert card.art_char_width == 6.0

    def test_explicit_values_win(self, tmp_path):
        card = self._card(tmp_path, "  portrait_font_size: 10\n"
                                    "  portrait_line_height: 11\n"
                                    "  portrait_char_width: 6.5\n")
        assert (card.art_font_size, card.art_line_height, card.art_char_width) == (10, 11, 6.5)


class TestPortraitSwitch:
    """Turning the portrait off, and what that does to the column count."""

    NO_PORTRAIT = """
    github:
      username: octocat
    themes:
      dark:
        output: dist/dark.svg
        bg: "#000"
        fg: "#fff"
    card:
      show_portrait: false
      fields:
        - label: OS
          value: Linux
    """

    def test_a_theme_needs_no_portrait_when_it_draws_none(self, tmp_path):
        cfg = Config.load(write(tmp_path, self.NO_PORTRAIT))
        assert cfg.themes[0].portrait == ""

    def test_columns_default_to_two_without_a_portrait(self, tmp_path):
        assert Config.load(write(tmp_path, self.NO_PORTRAIT)).card.column_count == 2

    def test_columns_default_to_one_with_a_portrait(self, tmp_path):
        assert Config.load(write(tmp_path, MINIMAL)).card.column_count == 1

    def test_an_explicit_column_count_wins(self, tmp_path):
        cfg = Config.load(write(tmp_path, self.NO_PORTRAIT + "  columns: 1\n"))
        assert cfg.card.column_count == 1

    def test_zero_columns_is_an_error(self, tmp_path):
        with pytest.raises(ConfigError, match="card.columns"):
            Config.load(write(tmp_path, self.NO_PORTRAIT + "  columns: 0\n"))

    def test_a_missing_portrait_is_still_an_error_when_one_is_drawn(self, tmp_path):
        from profilecard.render import render_theme

        missing = MINIMAL.replace("assets/portrait.txt", "assets/gone.txt")
        cfg = Config.load(write(tmp_path, missing))
        with pytest.raises(ConfigError, match="gone.txt"):
            render_theme(cfg, cfg.themes[0], {"username": "octocat"})

    def test_a_field_needs_a_label_a_separator_or_a_break(self, tmp_path):
        with pytest.raises(ConfigError, match="column_break"):
            Config.load(write(tmp_path, MINIMAL + "    - value: orphan\n"))
