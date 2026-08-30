"""Tests for the parts that silently produce a wrong-looking card when broken."""

import pytest

from profilecard.config import CardConfig, ConfigError, Field
from profilecard.render import (
    GRID_DAYS,
    GRID_WEEKS,
    _grid_cells,
    _grid_rows,
    _leader,
    build_columns,
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


class TestColumns:
    """The layout used when the portrait is off."""

    def _fields(self, *sizes):
        """Sections of the given sizes, separated."""
        out = []
        for n in sizes:
            if out:
                out.append(Field(separator=True))
            out.extend(Field(label=f"S{len(out)}.R{i}", value="x") for i in range(n))
        return out

    def _card(self, fields, **kw):
        kw.setdefault("show_portrait", False)
        return CardConfig(title="{username}", fields=fields, min_dots=2, **kw)

    def test_one_column_by_default_with_a_portrait(self):
        card = CardConfig(title="{username}", fields=self._fields(3, 3))
        assert len(build_columns(card, VALUES)[1]) == 1

    def test_two_columns_by_default_without_one(self):
        assert len(build_columns(self._card(self._fields(3, 3)), VALUES)[1]) == 2

    def test_split_minimises_the_tallest_column(self):
        # 1 / 3 / 10 / 4 / 1 rows: the only sensible cut is before the 4.
        _, columns = build_columns(self._card(self._fields(1, 3, 10, 4, 1)), VALUES)
        assert [len(c) for c in columns] == [16, 6]

    def test_sections_are_not_split_across_columns(self):
        # A cut inside the 10 would balance better, but sections stay whole.
        _, columns = build_columns(self._card(self._fields(2, 10)), VALUES)
        assert [len(c) for c in columns] == [2, 10]

    def test_column_break_overrides_the_balancer(self):
        fields = self._fields(2, 10)
        fields.insert(5, Field(column_break=True))
        _, columns = build_columns(self._card(fields), VALUES)
        assert [len(c) for c in columns] == [5, 8]

    def test_column_break_is_ignored_in_one_column(self):
        # Turning the portrait back on must not leave a blank line behind.
        fields = self._fields(2, 10)
        with_break = [*fields[:5], Field(column_break=True), *fields[5:]]
        plain = build_lines(self._card(fields, show_portrait=True), VALUES)
        assert len(build_lines(self._card(with_break, show_portrait=True), VALUES)) == len(plain)

    def test_each_column_aligns_its_own_values(self):
        # A long label on the left must not push the right column's values out
        # into a field of dots.
        fields = [Field(label="A.Very.Long.Label.Indeed", value="x"), Field(separator=True),
                  Field(label="B", value="y")]
        _, columns = build_columns(self._card(fields), VALUES)
        assert visible_length(columns[1][0].runs) == len(". B: .. y")

    def test_more_columns_than_sections_is_harmless(self):
        _, columns = build_columns(self._card(self._fields(2, 2), columns=9), VALUES)
        assert [len(c) for c in columns] == [2, 2]


class TestHeadings:
    """Section titles, and the group boundary they imply."""

    def _card(self, fields, **kw):
        kw.setdefault("show_portrait", False)
        return CardConfig(title="{username}", fields=fields, min_dots=2, **kw)

    def _lines(self, fields, **kw):
        return build_lines(self._card(fields, show_portrait=True, **kw), VALUES)[1:]

    def test_a_heading_renders_flush_left_with_no_rail(self):
        lines = self._lines([Field(heading="Stack"), Field(label="A", value="x")])
        assert [(r.text, r.style) for r in lines[0].runs] == [("Stack", "heading")]
        assert lines[0].heading

    def test_a_heading_opens_a_section_without_a_rail_dot(self):
        # The heading is the break; a rail dot on top of it is just clutter.
        lines = self._lines([
            Field(label="A", value="x"),
            Field(heading="Stack"),
            Field(label="B", value="y"),
        ])
        assert [visible_length(l.runs) for l in lines[:3]][1] == 0

    def test_a_leading_heading_gets_no_blank_line_above_it(self):
        lines = self._lines([Field(heading="Stack"), Field(label="A", value="x")])
        assert len(lines) == 2

    def test_a_heading_does_not_widen_the_label_column(self):
        # "A Very Long Heading" is not a label and must not pad the leaders out.
        short = self._lines([Field(heading="S"), Field(label="A", value="x")])
        long = self._lines([Field(heading="A Very Long Heading"), Field(label="A", value="x")])
        assert visible_length(short[1].runs) == visible_length(long[1].runs)

    def test_a_heading_starts_a_column_group(self):
        # Four one-row sections: the split lands between the second and third.
        fields = [f for i in range(4) for f in
                  (Field(heading=f"H{i}"), Field(label=f"L{i}", value="x"))]
        _, columns = build_columns(self._card(fields), VALUES)
        assert [len(c) for c in columns] == [5, 5]


class TestHeatmap:
    """The contribution grid: a block that occupies rows instead of text."""

    def _card(self, fields, **kw):
        kw.setdefault("show_portrait", False)
        return CardConfig(title="{username}", fields=fields, min_dots=2, **kw)

    RAMP = ["e", "1", "2", "3", "4"]

    def test_an_empty_calendar_still_fills_the_grid(self):
        # Offline builds have no numbers; the card must not change shape.
        cells = _grid_cells([], self.RAMP)
        assert len(cells) == GRID_WEEKS * GRID_DAYS
        assert {c[2] for c in cells} == {"e"}

    def test_a_day_with_no_activity_takes_the_quietest_shade(self):
        cells = _grid_cells([("2026-01-04", 0), ("2026-01-05", 9)], self.RAMP)
        assert cells[0][2] == "e"
        assert cells[1][2] != "e"

    def test_shading_is_square_root_not_linear(self):
        # Against a peak of 100, a linear ramp would bucket 10 into the quietest
        # active shade and the whole year would read dead.
        cells = _grid_cells([("2026-01-04", 10), ("2026-01-05", 100)], self.RAMP)
        assert cells[0][2] == "2"
        assert cells[1][2] == "4"

    def test_weeks_advance_on_sundays(self):
        # 2026-01-04 is a Sunday, so the following Sunday starts column 1.
        days = [(f"2026-01-{d:02d}", 1) for d in range(4, 13)]
        cells = _grid_cells(days, self.RAMP)
        assert [c[0] for c in cells] == [0] * 7 + [1, 1]
        assert cells[0][1] == 0  # Sunday sits on the top row

    def test_the_grid_claims_several_rows(self):
        card = self._card([], heat_cell=7, heat_gap=2)
        assert _grid_rows(card) > 1

    def test_the_splitter_counts_those_rows(self):
        # A grid worth 4 rows must not be balanced as though it were one line.
        rows = _grid_rows(self._card([]))
        fields = [Field(label="A", value="x"), Field(separator=True),
                  Field(heatmap="contributions")]
        _, columns = build_columns(self._card(fields), VALUES)
        assert [len(c) for c in columns] == [1, rows]

    def test_the_column_is_widened_to_fit_the_grid(self):
        # The grid has no text, so without min_cols the column would collapse.
        _, columns = build_columns(self._card([Field(heatmap="contributions")]), VALUES)
        assert columns[0][0].min_cols > 40


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
