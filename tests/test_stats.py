"""Tests for the contribution-calendar and language maths."""

import pytest

from profilecard.github import Stats, read_calendar, top_languages


def calendar(counts, start_day=1):
    """Build the week/day shape GitHub returns from a flat list of counts."""
    days = [
        {"date": f"2026-01-{i + start_day:02d}", "contributionCount": c}
        for i, c in enumerate(counts)
    ]
    return {"weeks": [{"contributionDays": days}], "totalContributions": sum(counts)}


class TestReadCalendar:
    def test_counts_active_days_not_calendar_days(self):
        cal = read_calendar(calendar([0, 3, 0, 5, 0]))
        assert cal.active_days == 2
        assert cal.total_days == 5

    def test_averages_distinguish_per_day_from_per_active_day(self):
        cal = read_calendar(calendar([0, 0, 10, 10]))
        assert cal.per_day == 5.0
        assert cal.per_active_day == 10.0

    def test_longest_streak_spans_the_best_run(self):
        assert read_calendar(calendar([1, 1, 0, 1, 1, 1, 0, 1])).longest_streak == 3

    def test_current_streak_counts_back_from_the_end(self):
        assert read_calendar(calendar([1, 0, 1, 1, 1])).current_streak == 3

    def test_an_empty_today_does_not_break_the_streak(self):
        # The nightly build runs at 04:00, before any commits exist for today.
        # Counting today as a miss would report a broken streak every morning.
        assert read_calendar(calendar([1, 1, 1, 0])).current_streak == 3

    def test_two_empty_days_does_break_it(self):
        assert read_calendar(calendar([1, 1, 0, 0])).current_streak == 0

    def test_busiest_day_reports_count_and_date(self):
        cal = read_calendar(calendar([3, 9, 4]))
        assert cal.busiest_count == 9
        assert cal.busiest_date == "2026-01-02"

    def test_empty_calendar_does_not_divide_by_zero(self):
        cal = read_calendar({"weeks": [], "totalContributions": 0})
        assert (cal.per_day, cal.per_active_day, cal.longest_streak) == (0.0, 0.0, 0)

    def test_no_active_days_does_not_divide_by_zero(self):
        assert read_calendar(calendar([0, 0, 0])).per_active_day == 0.0


def repo(**langs):
    return {"languages": {"edges": [
        {"size": size, "node": {"name": name}} for name, size in langs.items()
    ]}}


class TestTopLanguages:
    def test_sums_bytes_across_repositories(self):
        # Python appears in both repos and must be added together, not replaced.
        result = top_languages([repo(Python=100), repo(Python=300, Go=600)])
        assert result == [("Go", 60.0), ("Python", 40.0)]

    def test_orders_by_size_descending(self):
        names = [n for n, _ in top_languages([repo(A=1, B=50, C=10)])]
        assert names == ["B", "C", "A"]

    def test_percentages_sum_to_one_hundred(self):
        total = sum(p for _, p in top_languages([repo(A=3, B=5, C=7)]))
        assert total == pytest.approx(100.0)

    def test_respects_the_limit(self):
        assert len(top_languages([repo(A=1, B=2, C=3, D=4)], limit=2)) == 2

    def test_no_languages_is_empty_not_an_error(self):
        assert top_languages([{"languages": {"edges": []}}]) == []


class TestStatsDefaults:
    def test_loc_is_added_minus_deleted(self):
        assert Stats(username="x", loc_added=500, loc_deleted=200).loc == 300
