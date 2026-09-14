"""Tests for the banner's fixed canvas.

The card grows to fit its content, so its failure mode is a card of an odd
size.  The banner cannot grow, so its failure modes are all invisible from the
SVG itself: text off the canvas, text outside the crop a phone shows, text
under the profile photo.  These are the checks that catch those.
"""

import pytest

from profilecard.banner import (
    AVATAR_BOX,
    AVATAR_RING_X,
    MOBILE_PHOTO_Y,
    layout,
    layout_hero,
    render,
)
from profilecard.config import (
    BannerConfig,
    ConfigError,
    Field,
    HeroConfig,
    HeroLine,
    Theme,
)

VALUES = {"username": "octocat", "name": "Mona", "commits": "1,234", "prs": "12"}

THEME = Theme(
    name="dark", output="", portrait="", bg="#000", fg="#fff", key="#f80",
    value="#08f", dim="#888", add="#0a0", delete="#a00", rule="#333",
    heading="#fff", heat=["#111"] * 5,
)


def banner(**kw) -> BannerConfig:
    fields = kw.pop("fields", [
        Field(heading="Commits"),
        Field(label="All time", value="{commits}"),
        Field(column_break=True),
        Field(heading="Shipped"),
        Field(label="Pull requests", value="{prs} merged"),
    ])
    return BannerConfig(fields=fields, **kw)


class TestCanvas:
    def test_the_svg_is_exactly_the_configured_size(self):
        svg, _ = render(banner(), THEME, VALUES)
        assert 'width="1584px" height="396px"' in svg
        assert 'viewBox="0 0 1584 396"' in svg

    def test_content_is_centred_on_the_canvas(self):
        box = layout(banner(), VALUES)
        left = box["x0"]
        right = 1584 - (box["x0"] + box["block_w"])
        # Centred, not left-aligned: the phone crop takes from both edges.
        assert abs(left - right) <= 1

    def test_offset_shifts_the_block_off_centre(self):
        box = layout(banner(offset_x=40), VALUES)
        assert box["x0"] == layout(banner(), VALUES)["x0"] + 40

    def test_content_that_does_not_fit_is_an_error(self):
        # The card would simply have grown. A banner cannot, and a silently
        # clipped one is worse than a failed build.
        tall = [Field(label=f"Row {i}", value="x") for i in range(40)]
        with pytest.raises(ConfigError) as exc:
            layout(banner(fields=tall, columns=1), VALUES)
        assert "does not fit" in str(exc.value)


class TestWarnings:
    def test_no_warnings_when_the_block_clears_everything(self):
        assert layout(banner(), VALUES)["warnings"] == []

    def test_wide_content_warns_about_the_mobile_crop(self):
        box = layout(banner(safe_width=100), VALUES)
        assert any("cropped from each side" in w for w in box["warnings"])

    # Wide enough that the centred block reaches left of the photo's edge;
    # depth is then the only variable between the next two tests.
    WIDE = "x" * 70

    def test_a_deep_left_column_warns_about_the_profile_photo(self):
        deep = [Field(label=f"Row {i}", value=self.WIDE) for i in range(11)]
        box = layout(banner(fields=deep, columns=1), VALUES)
        assert box["x0"] < AVATAR_BOX[2]
        assert any("profile photo" in w for w in box["warnings"])

    def test_a_shallow_left_column_does_not(self):
        # The whole point of putting the short section on the left: the photo
        # covers that corner, so the column that ends early belongs there.
        shallow = [Field(label=f"Row {i}", value=self.WIDE) for i in range(3)]
        box = layout(banner(fields=shallow, columns=1), VALUES)
        assert box["x0"] < AVATAR_BOX[2]
        assert not any("profile photo" in w for w in box["warnings"])


class TestWrapping:
    LONG = [
        Field(heading="Stack"),
        Field(label="Primary", value="Python, TypeScript, JavaScript, PLpgSQL, Mako"),
    ]

    def test_wrapping_keeps_the_column_inside_its_cap(self):
        box = layout(banner(fields=self.LONG, columns=1, wrap_cols=30), VALUES)
        assert box["col_widths"][0] <= 30

    def test_wrapping_trades_width_for_height(self):
        wide = layout(banner(fields=self.LONG, columns=1), VALUES)
        tall = layout(banner(fields=self.LONG, columns=1, wrap_cols=30), VALUES)
        assert tall["block_w"] < wide["block_w"]
        assert tall["block_h"] > wide["block_h"]

    def test_continuation_rows_are_indented_to_the_value(self):
        box = layout(banner(fields=self.LONG, columns=1, wrap_cols=30), VALUES)
        rows = box["columns"][0]
        # Row 0 is the heading, row 1 opens the value, row 2 continues it.
        assert rows[2].runs[0].text.strip() == ""
        assert len(rows[2].runs[0].text) > 2  # indented past the ". " rail

    def test_no_wrap_cols_leaves_one_row_per_field(self):
        # What the card passes. Its layout must not change.
        box = layout(banner(fields=self.LONG, columns=1), VALUES)
        assert len(box["columns"][0]) == 2


class TestConfig:
    def test_char_width_defaults_to_the_monospace_advance(self):
        assert BannerConfig(font_size=20).char_width == 12.0

    def test_as_card_drops_the_title(self):
        # A title left in would be measured at the body size and would widen
        # the columns to match it.
        assert banner().as_card().title == ""

    def test_a_heatmap_is_refused(self):
        with pytest.raises(ConfigError) as exc:
            BannerConfig.parse({"fields": [{"heatmap": "contributions"}]})
        assert "fixed canvas" in str(exc.value)

    def test_enabled_false_is_the_same_as_absent(self):
        # So a banner still being designed leaves nothing for the nightly job
        # to commit to a public repository.
        assert BannerConfig.parse({"enabled": False, "font_size": 20}) is None
        assert BannerConfig.parse({"enabled": True, "font_size": 20}) is not None

    def test_a_switched_off_banner_is_still_validated(self):
        # Otherwise a typo sits undiscovered until the day it is switched on.
        with pytest.raises(ConfigError) as exc:
            BannerConfig.parse({"enabled": False, "widht": 1584})
        assert "widht" in str(exc.value)

    def test_unknown_keys_are_refused(self):
        with pytest.raises(ConfigError) as exc:
            BannerConfig.parse({"widht": 1584})
        assert "widht" in str(exc.value)

    def test_field_errors_name_the_banner_not_the_card(self):
        with pytest.raises(ConfigError) as exc:
            BannerConfig.parse({"fields": [{"value": "orphan"}]})
        assert "banner.fields[0]" in str(exc.value)


class TestHero:
    """The hero layout. Its failure modes are all invisible in the SVG: the
    canvas is the right size either way, and the text is simply gone once
    LinkedIn has cropped it or dropped a photo on top of it."""

    def hero(self, **kw):
        lines = kw.pop("lines", [HeroLine(text="Still writing code.", size=66)])
        return HeroConfig(lines=lines, **kw)

    def test_baselines_stack_by_size_and_gap(self):
        h = self.hero(top=50, lines=[
            HeroLine(text="a", size=20),
            HeroLine(text="b", size=30, gap=10),
        ])
        assert [y for y, *_ in layout_hero(h, VALUES)["placed"]] == [70, 110]

    def test_a_line_overrunning_the_phone_crop_warns(self):
        h = self.hero(x=400, right=600, lines=[HeroLine(text="x" * 80, size=30)])
        warnings = layout_hero(h, VALUES)["warnings"]
        assert any("past the phone crop" in w for w in warnings)

    def test_the_warning_says_what_size_would_fit(self):
        h = self.hero(x=400, right=600, lines=[HeroLine(text="x" * 80, size=30)])
        warning = next(w for w in layout_hero(h, VALUES)["warnings"] if "crop" in w)
        assert "px" in warning.split("drop it to")[1]

    def test_text_inside_the_photo_ring_warns(self):
        h = self.hero(x=AVATAR_RING_X - 1)
        assert any("ring" in w for w in layout_hero(h, VALUES)["warnings"])

    def test_text_below_the_floor_warns(self):
        h = self.hero(top=500, floor=290)
        assert any("floor" in w for w in layout_hero(h, VALUES)["warnings"])
        assert any(str(MOBILE_PHOTO_Y) in w for w in layout_hero(h, VALUES)["warnings"])

    def test_a_clean_hero_warns_about_nothing(self):
        assert layout_hero(self.hero(), VALUES)["warnings"] == []

    def test_hero_renders_without_columns(self):
        b = BannerConfig(hero=self.hero(), fields=[])
        svg, _ = render(b, THEME, VALUES)
        assert "Still writing code." in svg
        assert 'width="1584px" height="396px"' in svg

    def test_an_unknown_style_is_refused(self):
        with pytest.raises(ConfigError) as exc:
            HeroLine.parse({"text": "x", "size": 20, "style": "chartreuse"}, 0)
        assert "chartreuse" in str(exc.value)

    def test_hero_needs_lines(self):
        with pytest.raises(ConfigError) as exc:
            HeroConfig.parse({"x": 400})
        assert "non-empty" in str(exc.value)


class TestPaletteOnlyThemes:
    def test_a_palette_only_theme_needs_no_output(self):
        t = Theme.parse("oxblood", {"card": False, "bg": "#000", "fg": "#fff"})
        assert t.card is False and t.output == ""

    def test_a_card_theme_still_requires_one(self):
        with pytest.raises(ConfigError) as exc:
            Theme.parse("dark", {"bg": "#000", "fg": "#fff"})
        assert "output" in str(exc.value)
