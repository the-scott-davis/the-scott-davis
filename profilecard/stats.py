"""Collect the numbers the card displays, and turn them into placeholder values."""

from __future__ import annotations

import datetime
from typing import Any

from dateutil import relativedelta

from .cache import Entry, LocCache
from .config import Config
from .github import (
    Client,
    Stats,
    collect_profile,
    commit_hours,
    contribution_totals,
    fetch_repo_signals,
    get_user,
    load_timezone,
    iter_repos,
    recent_repos,
    repo_loc,
    top_languages,
    weekday_totals,
)
from .techstack import rank


def humanize_age(birthday: datetime.date) -> str:
    """'40 years, 7 months, 21 days' -- with a cake on the day itself."""
    today = datetime.date.today()
    diff = relativedelta.relativedelta(today, birthday)
    parts = [
        f"{diff.years} year{'' if diff.years == 1 else 's'}",
        f"{diff.months} month{'' if diff.months == 1 else 's'}",
        f"{diff.days} day{'' if diff.days == 1 else 's'}",
    ]
    cake = " 🎂" if diff.months == 0 and diff.days == 0 else ""
    return ", ".join(parts) + cake


def _coerce_date(value: Any) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return None
    return None


def collect(cfg: Config, client: Client, *, verbose: bool = False) -> Stats:
    """Gather everything the card can show.

    Two phases with very different costs.  The profile phase is a couple of
    queries and gives commits, pull requests, streaks, and languages.  The line
    counting phase walks every commit of every repository and is off by default
    -- see ``github.count_lines``.
    """
    gh = cfg.github
    stats = Stats(username=gh.username)

    profile = collect_profile(client, gh.username, gh.affiliations)
    stats.followers = profile["followers"]
    stats.contributed = profile["contributed"]
    stats.prs_merged = profile["prs_merged"]
    stats.prs_open = profile["prs_open"]
    stats.issues_opened = profile["issues_opened"]
    stats.repos = profile["repos"]
    stats.stars = profile["stars"]
    stats.github_since = profile["created_at"][:4]
    stats.github_created = profile["created_at"][:10]

    # Recency first: GitHub's language stats have no sense of time, so one large
    # old service outranks everything current until you cut by push date.
    sc = cfg.stack
    fresh = recent_repos(profile["repo_nodes"], sc.since_years)
    stats.recent_repos = len(fresh)
    stats.languages = top_languages(fresh, sc.limit, set(sc.exclude_languages))

    # What they build *with*, which the languages API cannot see at all.
    signals = fetch_repo_signals(client, fresh)
    stats.tech = [(t.name, t.repos) for t in rank(signals, set(sc.exclude_tech))][: sc.limit]

    stats.weekdays = weekday_totals(profile["calendar_raw"])

    if sc.sample_repos:
        stats.hours = commit_hours(
            client,
            fresh[: sc.sample_repos],
            profile["id"],
            tz=load_timezone(sc.timezone),
            offset=sc.timezone_offset,
        )

    cal = profile["calendar"]
    stats.active_days = cal.active_days
    stats.calendar_days = cal.total_days
    stats.per_day = cal.per_day
    stats.per_active_day = cal.per_active_day
    stats.longest_streak = cal.longest_streak
    stats.current_streak = cal.current_streak
    stats.busiest_count = cal.busiest_count
    stats.busiest_date = cal.busiest_date

    # Commit counts come from the contributions API, the same source as the
    # graph on your profile.  Deriving them from a repository walk undercounts
    # badly: the walk only sees default branches of repositories the token can
    # read, so most private work never appears at all.
    for key, value in contribution_totals(client, gh.username, profile["created_at"]).items():
        setattr(stats, key, value)

    if verbose:
        print(f"  {stats.commits:,} commits, {stats.prs_merged:,} PRs merged, "
              f"{stats.active_days}/{stats.calendar_days} active days")
        print(f"  {stats.recent_repos} recent repos -> "
              f"{', '.join(n for n, _ in stats.tech[:6])}")

    if gh.count_lines:
        _collect_lines(cfg, client, stats, verbose=verbose)

    stats.api_calls = client.calls
    return stats


def _collect_lines(cfg: Config, client: Client, stats: Stats, *, verbose: bool = False) -> None:
    """Walk every commit of every repository. Slow, and cached aggressively."""
    gh = cfg.github
    user = get_user(client, gh.username)
    owner_id = user["id"]

    cache = LocCache()
    excluded = {r.lower() for r in gh.exclude_repos}
    live: set[str] = set()

    for repo in iter_repos(client, gh.username, gh.affiliations):
        name = repo["nameWithOwner"]
        if name.lower() in excluded:
            continue
        live.add(name)

        ref = repo.get("defaultBranchRef")
        if not ref:  # empty repository
            cache.put(name, Entry(head="", added=0, deleted=0, commits=0))
            continue

        head = ref["target"]["oid"]
        if cache.get(name, head) is None:
            if verbose:
                print(f"  walking {name}")
            added, deleted, commits = repo_loc(client, name, owner_id, gh.only_my_commits)
            cache.put(name, Entry(head=head, added=added, deleted=deleted, commits=commits))

    cache.prune(live)
    cache.save()
    stats.loc_added, stats.loc_deleted, _ = cache.totals()
    stats.cache_hits, stats.cache_misses = cache.hits, cache.misses


def offline_stats(cfg: Config) -> Stats:
    """Whatever the cache already knows, so the layout renders without a token.

    Commit counts are not cached -- they come from a single cheap API call, so
    there is nothing to replay offline and they render as zero.
    """
    stats = Stats(username=cfg.github.username)
    cache = LocCache()
    stats.loc_added, stats.loc_deleted, _ = cache.totals()
    stats.contributed = len(cache.entries)
    return stats


def to_values(cfg: Config, stats: Stats, github_name: str | None = None) -> dict[str, str]:
    """Everything a config field can reference as ``{placeholder}``."""
    values: dict[str, str] = {k: str(v) for k, v in cfg.vars.items()}

    birthday = _coerce_date(cfg.vars.get("birthday"))
    if birthday:
        values["age"] = humanize_age(birthday)
        values["birthday"] = birthday.isoformat()

    values.setdefault("name", github_name or cfg.github.username)
    values["username"] = cfg.github.username
    values["today"] = datetime.date.today().isoformat()

    for key in ("commits", "commits_public", "commits_private", "commits_year",
                "commits_ytd", "commits_prev_year", "contributions",
                "contributions_year", "stars", "repos", "contributed",
                "followers", "loc", "loc_added", "loc_deleted",
                "active_days", "calendar_days", "longest_streak",
                "current_streak", "busiest_count", "prs_merged", "prs_open",
                "issues_opened"):
        values[key] = f"{getattr(stats, key):,}"

    today = datetime.date.today()
    values["year"] = str(today.year)
    values["prev_year"] = str(today.year - 1)
    values["per_day"] = f"{stats.per_day:.1f}"
    values["per_active_day"] = f"{stats.per_active_day:.1f}"
    values["active_pct"] = (
        f"{stats.active_days / stats.calendar_days * 100:.0f}" if stats.calendar_days else "0"
    )
    values["busiest_date"] = stats.busiest_date
    values["github_since"] = stats.github_since

    langs = stats.languages or []
    values["languages"] = ", ".join(f"{n} {p:.0f}%" for n, p in langs[:4])
    # Skips the leader, so a card can show "Primary: X" and "Also: ..." without
    # naming X twice.
    values["languages_list"] = ", ".join(n for n, _ in langs[1:7])
    values["languages_all"] = ", ".join(n for n, _ in langs)
    values["language_top"] = langs[0][0] if langs else ""
    values["language_top_pct"] = f"{langs[0][1]:.0f}" if langs else "0"

    tech = stats.tech or []
    values["tech"] = ", ".join(n for n, _ in tech)
    values["tech_top"] = tech[0][0] if tech else ""
    for n in (3, 4, 5, 6):
        values[f"tech_{n}"] = ", ".join(name for name, _ in tech[:n])
    values["recent_repos"] = f"{stats.recent_repos:,}"

    if stats.github_created:
        values["github_age"] = humanize_age(_coerce_date(stats.github_created))

    weekdays = stats.weekdays or {}
    if weekdays:
        ranked = sorted(weekdays.items(), key=lambda kv: kv[1], reverse=True)
        values["busiest_weekday"] = ranked[0][0]
        values["busiest_weekday_count"] = f"{ranked[0][1]:,}"
        values["quietest_weekday"] = ranked[-1][0]
        weekend = weekdays.get("Saturday", 0) + weekdays.get("Sunday", 0)
        total = sum(weekdays.values()) or 1
        values["weekend_pct"] = f"{weekend / total * 100:.0f}"

    hours = stats.hours or {}
    if hours:
        peak = max(hours.items(), key=lambda kv: kv[1])
        total = sum(hours.values()) or 1
        # A two-hour window reads better than a single spiky hour.
        window = max(
            range(24), key=lambda h: hours.get(h, 0) + hours.get((h + 1) % 24, 0)
        )
        values["busiest_hour"] = f"{peak[0]:02d}:00"
        values["busiest_hour_pct"] = f"{peak[1] / total * 100:.0f}"
        values["busiest_window"] = f"{window:02d}:00-{(window + 2) % 24:02d}:00"
    return values
