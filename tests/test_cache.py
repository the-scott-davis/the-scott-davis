"""The cache must re-walk a repository whose branch head moved, and only then."""

from profilecard.cache import Entry, LocCache


def make(tmp_path):
    return LocCache(tmp_path / "loc.json")


def test_roundtrip(tmp_path):
    cache = make(tmp_path)
    cache.put("me/repo", Entry(head="abc", added=10, deleted=4, commits=2))
    cache.save()

    reloaded = LocCache(tmp_path / "loc.json")
    assert reloaded.totals() == (10, 4, 2)


def test_hit_requires_a_matching_head(tmp_path):
    cache = make(tmp_path)
    cache.put("me/repo", Entry(head="abc", added=1, deleted=0, commits=1))
    assert cache.get("me/repo", "abc") is not None
    # A force-push or amend changes the SHA without changing the commit count,
    # which is exactly the case a count-based cache gets wrong.
    assert cache.get("me/repo", "def") is None
    assert (cache.hits, cache.misses) == (1, 1)


def test_unknown_repo_is_a_miss(tmp_path):
    assert make(tmp_path).get("me/other", "abc") is None


def test_prune_drops_repos_that_are_gone(tmp_path):
    cache = make(tmp_path)
    cache.put("me/keep", Entry("a", 1, 0, 1))
    cache.put("me/gone", Entry("b", 5, 0, 1))
    cache.prune({"me/keep"})
    # Entries are keyed by hash, so assert through the public lookup.
    assert len(cache.entries) == 1
    assert cache.get("me/keep", "a") is not None
    assert cache.get("me/gone", "b") is None


def test_schema_bump_invalidates(tmp_path):
    path = tmp_path / "loc.json"
    path.write_text('{"schema": 0, "repos": {"me/r": {"head":"a","added":9,"deleted":0,"commits":1}}}')
    assert LocCache(path).totals() == (0, 0, 0)


def test_repo_names_are_never_written_in_the_clear(tmp_path):
    # This file is committed to a public repository. Private repository names
    # must not leak into it as a side effect of caching.
    cache = make(tmp_path)
    cache.put("acme/super-secret-project", Entry("abc", 1, 0, 1))
    cache.save()
    published = (tmp_path / "loc.json").read_text()
    assert "super-secret-project" not in published
    assert "acme" not in published
    # ...and it still round-trips.
    assert LocCache(tmp_path / "loc.json").get("acme/super-secret-project", "abc") is not None


def test_corrupt_cache_rebuilds_instead_of_crashing(tmp_path):
    path = tmp_path / "loc.json"
    path.write_text("{not json")
    assert LocCache(path).totals() == (0, 0, 0)
