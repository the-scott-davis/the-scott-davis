"""Tests for the banner's fixed canvas.

The card grows to fit its content, so its failure mode is a card of an odd
size.  The banner cannot grow, so its failure modes are all invisible from the
SVG itself: text off the canvas, text outside the crop a phone shows, text
under the profile photo.  These are the checks that catch those.
"""

import pytest

from profilecard.banner import AVATAR_BOX, layout, render
from profilecard.config import BannerConfig, ConfigError, Field, Theme

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
