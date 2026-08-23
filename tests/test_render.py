"""Tests for the parts that silently produce a wrong-looking card when broken."""

import pytest

from profilecard.config import CardConfig, ConfigError, Field
from profilecard.render import (
    _leader,
    build_lines,
    parse_markup,
    substitute,
    visible_length,
    xml_escape,
)

VALUES = {"username": "octocat", "name": "Mona", "commits": "1,234"}


class TestSubstitute:
    def test_expands_known_placeholders(self):
        assert substitute("{name} has {commits}", VALUES, "t") == "Mona has 1,234"

    def test_unknown_placeholder_is_an_error(self):
        # A silent blank would ship a typo to the world.
        with pytest.raises(ConfigError) as exc:
            substitute("{discrod}", VALUES, "card.fields[3]")
        assert "discrod" in str(exc.value)
        assert "card.fields[3]" in str(exc.value)

    def test_doubled_braces_stay_literal(self):
        assert substitute("{{Contributed}}", VALUES, "t") == "{Contributed}"

    def test_doubled_braces_around_a_placeholder(self):
        assert substitute("{{{name}}}", VALUES, "t") == "{Mona}"


class TestMarkup:
    def test_splits_into_styled_runs(self):
        runs = parse_markup("a <add>b</add> c")
        assert [(r.text, r.style) for r in runs] == [("a ", None), ("b", "add"), (" c", None)]

    def test_visible_length_ignores_tags(self):
        assert visible_length(parse_markup("<dim>(</dim>12<dim>)</dim>")) == 4

    def test_unclosed_tag_is_an_error(self):
        with pytest.raises(ConfigError, match="unclosed"):
            parse_markup("a <add>b")

    def test_nested_tags_are_an_error(self):
        with pytest.raises(ConfigError, match="nested"):
            parse_markup("<add>a <del>b</del></add>")

    def test_unknown_tags_are_left_as_text(self):
        assert parse_markup("<b>x</b>")[0].text == "<b>x</b>"


class TestLeader:
    @pytest.mark.parametrize("width", range(0, 12))
    def test_leader_is_exactly_the_requested_width(self, width):
        # The whole column alignment rests on this being exact.
        assert len(_leader(width)) == width

    def test_leader_is_padded_away_from_the_text(self):
        assert _leader(6) == " .... "


class TestBuildLines:
    def _card(self, fields):
        return CardConfig(title="{username}", fields=fields, min_dots=2)

    def test_all_values_start_in_the_same_column(self):
        card = self._card([
            Field(label="OS", value="macOS"),
            Field(label="A.Very.Long.Label", value="x"),
        ])
        lines = build_lines(card, VALUES)[1:]  # skip the title
        starts = []
        for line in lines:
            offset = 0
            for run in line.runs:
                if run.style == "dim" and "." in run.text and run.text.endswith(" "):
                    offset += len(run.text)
                    starts.append(offset)
                    break
                offset += len(run.text)
        assert len(set(starts)) == 1

    def test_separator_produces_a_near_empty_line(self):
        lines = build_lines(self._card([Field(separator=True)]), VALUES)
        assert visible_length(lines[1].runs) <= 2

    def test_removing_a_field_removes_exactly_one_line(self):
        both = build_lines(self._card([
            Field(label="Email", value="a@b.c"),
            Field(label="Discord", value="x"),
        ]), VALUES)
        one = build_lines(self._card([Field(label="Email", value="a@b.c")]), VALUES)
        assert len(both) - len(one) == 1

    def test_dotted_label_renders_as_nested_keys(self):
        lines = build_lines(self._card([Field(label="Languages.Real", value="English")]), VALUES)
        keys = [r.text for r in lines[1].runs if r.style == "key"]
        assert keys == ["Languages", "Real"]


class TestEscaping:
    def test_xml_special_characters_are_escaped(self):
        assert xml_escape('a & b <c> "d"') == "a &amp; b &lt;c&gt; &quot;d&quot;"


class TestRamps:
    def test_measured_ramps_run_light_to_dark(self):
        from profilecard.ascii_art import RAMPS
        for name in ("measured", "measured32", "silhouette"):
            ramp = RAMPS[name]
            assert ramp[0] == " ", f"{name} should start with a blank"
            assert len(set(ramp)) == len(ramp), f"{name} has a duplicate character"
            assert len(ramp) >= 2
