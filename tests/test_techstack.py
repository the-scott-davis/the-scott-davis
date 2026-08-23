"""Tests for detecting what someone builds with, and for recency filtering."""

import datetime
import json

from profilecard.github import recent_repos, top_languages
from profilecard.techstack import rank, signals_for_repo


def pkg(**deps):
    return json.dumps({"dependencies": deps})


class TestSignals:
    def test_scope_prefixes_match_any_package_in_the_scope(self):
        found = signals_for_repo(pkg(**{"@aws-sdk/client-s3": "3"}), [])
        assert "AWS" in found

    def test_exact_names_do_not_match_by_prefix(self):
        # "pg" must not be triggered by "pg-boss-adjacent" style names.
        assert "Postgres" not in signals_for_repo(pkg(**{"pgstuff": "1"}), [])
        assert "Postgres" in signals_for_repo(pkg(pg="8"), [])

    def test_dev_dependencies_count(self):
        found = signals_for_repo(json.dumps({"devDependencies": {"vitest": "1"}}), [])
        assert "Vitest" in found

    def test_a_package_json_implies_node(self):
        assert "Node.js" in signals_for_repo(pkg(left_pad="1"), [])

    def test_marker_files_are_matched_case_insensitively(self):
        assert "Docker" in signals_for_repo(None, ["Dockerfile"])
        assert "Vercel" in signals_for_repo(None, [".vercelignore"])

    def test_no_package_json_means_no_node(self):
        assert "Node.js" not in signals_for_repo(None, ["main.tf"])

    def test_malformed_json_does_not_raise(self):
        # A file named package.json is still Node evidence even if the contents
        # are broken, so Node.js stays; what matters is that nothing throws and
        # the file signals still land.
        found = signals_for_repo("{not json", ["go.mod"])
        assert "Go" in found
        assert "Node.js" in found

    def test_empty_repo_yields_nothing(self):
        assert signals_for_repo(None, []) == set()


class TestRank:
    def test_ranks_by_how_many_repos_use_it(self):
        ranked = rank([{"React", "AWS"}, {"React"}, {"React", "AWS"}])
        assert [(t.name, t.repos) for t in ranked] == [("React", 3), ("AWS", 2)]

    def test_ties_break_alphabetically_for_stability(self):
        # Otherwise the card reshuffles between nightly builds for no reason.
        assert [t.name for t in rank([{"Zed", "Ada"}])] == ["Ada", "Zed"]

    def test_exclusions_are_case_insensitive(self):
        assert [t.name for t in rank([{"React", "PHP"}], exclude={"php"})] == ["React"]


class TestRecentRepos:
    def _repos(self):
        today = datetime.date.today()
        return [
            {"nameWithOwner": "a/new", "pushedAt": f"{today}T00:00:00Z"},
            {"nameWithOwner": "a/old",
             "pushedAt": f"{today - datetime.timedelta(days=900)}T00:00:00Z"},
        ]

    def test_filters_by_push_date(self):
        assert [r["nameWithOwner"] for r in recent_repos(self._repos(), 1)] == ["a/new"]

    def test_none_keeps_everything(self):
        assert len(recent_repos(self._repos(), None)) == 2

    def test_a_wide_window_keeps_everything(self):
        assert len(recent_repos(self._repos(), 5)) == 2


class TestLanguageExclusion:
    def _repos(self):
        return [{"languages": {"edges": [
            {"size": 900, "node": {"name": "C#"}},
            {"size": 100, "node": {"name": "TypeScript"}},
        ]}}]

    def test_excluding_the_leader_rescales_the_rest(self):
        # This is the whole point: drop a dead stack and the percentages must
        # re-normalise, not leave TypeScript reading 10%.
        result = top_languages(self._repos(), exclude={"C#"})
        assert result == [("TypeScript", 100.0)]

    def test_exclusion_is_case_insensitive(self):
        assert top_languages(self._repos(), exclude={"c#"}) == [("TypeScript", 100.0)]

    def test_excluding_everything_is_empty_not_an_error(self):
        assert top_languages(self._repos(), exclude={"C#", "TypeScript"}) == []
