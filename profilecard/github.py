"""A thin, well-behaved GitHub GraphQL client plus the stat collection on top.

Differences from the project this is modelled on that actually matter in CI:
retries with backoff instead of dying on a transient 502, real timeouts, an
explicit message when the token is missing a scope, and a rate-limit read so a
failure tells you *why* rather than dumping a raw status code.
"""

from __future__ import annotations

import datetime
import os
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

import requests

API_URL = "https://api.github.com/graphql"
TIMEOUT = 30
MAX_RETRIES = 4
RETRY_STATUSES = {429, 500, 502, 503, 504}


class GitHubError(RuntimeError):
    pass


@dataclass
class Stats:
    username: str
    followers: int = 0
    stars: int = 0
    repos: int = 0
    contributed: int = 0
    # Commits and contributions come from GitHub's contributions API -- the same
    # source as the graph on your profile page -- not from walking repositories.
    # Walking only sees default branches of repositories the token can read, and
    # misses everything else.
    commits: int = 0
    commits_public: int = 0
    commits_private: int = 0
    commits_year: int = 0
    contributions: int = 0
    contributions_year: int = 0
    commits_ytd: int = 0
    commits_prev_year: int = 0

    # Derived from the contribution calendar -- the day-by-day grid on your
    # profile.  It includes private activity, so unlike most of this API it
    # reflects the whole picture rather than just public work.
    active_days: int = 0
    calendar_days: int = 365
    per_day: float = 0.0
    per_active_day: float = 0.0
    longest_streak: int = 0
    current_streak: int = 0
    busiest_count: int = 0
    busiest_date: str = ""
    github_since: str = ""  # year the account was created

    prs_merged: int = 0
    prs_open: int = 0
    issues_opened: int = 0
    languages: list = None  # [(name, percent), ...] by bytes, largest first
    tech: list = None  # [(name, repo count), ...] detected from manifests
    weekdays: dict = None  # {"Monday": n, ...}
    hours: dict = None  # {local hour: n, ...} from a sample of recent commits
    recent_repos: int = 0
    github_created: str = ""
    loc_added: int = 0
    loc_deleted: int = 0
    api_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    @property
    def loc(self) -> int:
        return self.loc_added - self.loc_deleted


class Client:
    def __init__(self, token: str, *, verbose: bool = False):
        if not token:
            raise GitHubError(
                "No token. Set GITHUB_TOKEN (or ACCESS_TOKEN) to a personal access "
                "token with read access to repository contents and metadata."
            )
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "profilecard",
            }
        )
        self.calls = 0
        self.verbose = verbose

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict:
        payload = {"query": query, "variables": variables or {}}
        last_error = ""
        for attempt in range(MAX_RETRIES):
            self.calls += 1
            try:
                resp = self.session.post(API_URL, json=payload, timeout=TIMEOUT)
            except requests.RequestException as exc:
                last_error = str(exc)
                time.sleep(2**attempt)
                continue

            if resp.status_code == 401:
                raise GitHubError("401 Unauthorized -- the token is invalid or expired.")
            if resp.status_code == 403 and "rate limit" in resp.text.lower():
                raise GitHubError(f"Rate limited by GitHub: {resp.text[:200]}")
            if resp.status_code == 403:
                raise GitHubError(
                    f"403 Forbidden -- the token is probably missing a scope. {resp.text[:200]}"
                )
            if resp.status_code in RETRY_STATUSES:
                last_error = f"HTTP {resp.status_code}"
                time.sleep(2**attempt)
                continue
            if resp.status_code != 200:
                raise GitHubError(f"HTTP {resp.status_code}: {resp.text[:300]}")

            body = resp.json()
            if body.get("errors"):
                messages = "; ".join(e.get("message", "?") for e in body["errors"])
                # A missing repo mid-pagination shouldn't kill the whole run.
                if all(e.get("type") == "NOT_FOUND" for e in body["errors"]):
                    return {}
                raise GitHubError(f"GraphQL error: {messages}")
            return body["data"]

        raise GitHubError(f"Gave up after {MAX_RETRIES} attempts: {last_error}")


USER_QUERY = """
query($login: String!) {
  user(login: $login) {
    id
    login
    name
    createdAt
    followers { totalCount }
  }
}
"""

REPOS_QUERY = """
query($login: String!, $affiliations: [RepositoryAffiliation], $cursor: String) {
  user(login: $login) {
    repositories(first: 100, after: $cursor, ownerAffiliations: $affiliations,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        isFork
        stargazerCount
        owner { login }
        defaultBranchRef {
          name
          target { ... on Commit { oid history { totalCount } } }
        }
      }
    }
  }
}
"""

HISTORY_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            pageInfo { hasNextPage endCursor }
            nodes {
              additions
              deletions
              author { user { id } }
            }
          }
        }
      }
    }
  }
}
"""


def get_user(client: Client, login: str) -> dict:
    data = client.query(USER_QUERY, {"login": login})
    user = (data or {}).get("user")
    if not user:
        raise GitHubError(f"No such GitHub user: {login!r}")
    return user


def iter_repos(client: Client, login: str, affiliations: list[str]) -> Iterator[dict]:
    cursor = None
    while True:
        data = client.query(
            REPOS_QUERY, {"login": login, "affiliations": affiliations, "cursor": cursor}
        )
        repos = (data or {}).get("user", {}).get("repositories")
        if not repos:
            return
        yield from repos["nodes"]
        if not repos["pageInfo"]["hasNextPage"]:
            return
        cursor = repos["pageInfo"]["endCursor"]


def count_repos(client: Client, login: str, affiliations: list[str]) -> int:
    data = client.query(REPOS_QUERY, {"login": login, "affiliations": affiliations, "cursor": None})
    return (data or {}).get("user", {}).get("repositories", {}).get("totalCount", 0)


def repo_loc(client: Client, repo: str, owner_id: str, only_mine: bool) -> tuple[int, int, int]:
    """Walk a repository's default branch. Returns (added, deleted, commits)."""
    owner, name = repo.split("/", 1)
    added = deleted = commits = 0
    cursor = None
    while True:
        data = client.query(HISTORY_QUERY, {"owner": owner, "name": name, "cursor": cursor})
        ref = (data or {}).get("repository", {}).get("defaultBranchRef")
        if not ref:  # empty repository
            return added, deleted, commits
        history = ref["target"]["history"]
        for node in history["nodes"]:
            if only_mine:
                author = (node.get("author") or {}).get("user") or {}
                if author.get("id") != owner_id:
                    continue
            added += node["additions"]
            deleted += node["deletions"]
            commits += 1
        if not history["pageInfo"]["hasNextPage"]:
            return added, deleted, commits
        cursor = history["pageInfo"]["endCursor"]


PROFILE_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!,
      $affiliations: [RepositoryAffiliation], $cursor: String) {
  user(login: $login) {
    id
    createdAt
    followers { totalCount }
    repositoriesContributedTo(includeUserRepositories: true,
        contributionTypes: [COMMIT, PULL_REQUEST, REPOSITORY]) { totalCount }
    prsMerged: pullRequests(states: MERGED) { totalCount }
    prsOpen: pullRequests(states: OPEN) { totalCount }
    issues { totalCount }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
    repositories(first: 100, after: $cursor, ownerAffiliations: $affiliations, isFork: false) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        nameWithOwner
        pushedAt
        stargazerCount
        languages(first: 12, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""


@dataclass
class Calendar:
    """What the contribution grid says once you actually read it."""

    total: int = 0
    active_days: int = 0
    total_days: int = 0
    per_day: float = 0.0
    per_active_day: float = 0.0
    longest_streak: int = 0
    current_streak: int = 0
    busiest_count: int = 0
    busiest_date: str = ""


def read_calendar(calendar: dict) -> Calendar:
    """Turn the week/day grid into streaks and averages."""
    days = [d for week in calendar["weeks"] for d in week["contributionDays"]]
    if not days:
        return Calendar()
    counts = [d["contributionCount"] for d in days]
    active = [c for c in counts if c > 0]

    longest = run = 0
    for c in counts:
        run = run + 1 if c else 0
        longest = max(longest, run)

    # Count the current streak back from the end, but let today be empty: a
    # build that runs at 04:00 would otherwise report a broken streak every day.
    tail = counts[:-1] if counts and counts[-1] == 0 else counts
    current = 0
    for c in reversed(tail):
        if not c:
            break
        current += 1

    peak = max(counts)
    return Calendar(
        total=sum(counts),
        active_days=len(active),
        total_days=len(counts),
        per_day=sum(counts) / len(counts),
        per_active_day=(sum(active) / len(active)) if active else 0.0,
        longest_streak=longest,
        current_streak=current,
        busiest_count=peak,
        busiest_date=days[counts.index(peak)]["date"],
    )


def recent_repos(repos: list[dict], years: float | None) -> list[dict]:
    """Repositories pushed to within ``years``.  ``None`` keeps everything."""
    if not years:
        return repos
    cutoff = datetime.date.today() - datetime.timedelta(days=int(years * 365.25))
    return [r for r in repos if r.get("pushedAt", "")[:10] >= cutoff.isoformat()]


def top_languages(
    repos: list[dict], limit: int = 6, exclude: set[str] | None = None
) -> list[tuple[str, float]]:
    """Aggregate language bytes across repositories into percentages.

    Bytes are what GitHub measures, and they are a blunt instrument: a single
    large legacy service outweighs every recent project combined, and markup
    inflates against real code.  Filter by ``recent_repos`` and ``exclude``
    rather than trusting the raw ranking.
    """
    exclude = {e.lower() for e in (exclude or set())}
    totals: dict[str, int] = {}
    for repo in repos:
        for edge in repo.get("languages", {}).get("edges", []):
            name = edge["node"]["name"]
            if name.lower() in exclude:
                continue
            totals[name] = totals.get(name, 0) + edge["size"]
    grand = sum(totals.values())
    if not grand:
        return []
    ranked = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    return [(name, size / grand * 100) for name, size in ranked[:limit]]


CONTRIB_FIELDS = """
      totalCommitContributions
      restrictedContributionsCount
      contributionCalendar { totalContributions }
"""


def contribution_totals(client: Client, login: str, created_at: str) -> dict[str, int]:
    """Commit and contribution totals, lifetime and trailing year.

    ``contributionsCollection`` accepts at most a one-year window, so lifetime
    figures mean one window per calendar year since the account was created.
    They are aliased into a single query rather than sent one at a time.

    ``restrictedContributionsCount`` is GitHub's aggregate of activity in private
    repositories.  It is the only way to see that work at all -- the API will not
    say which repositories it came from -- but it counts every contribution type,
    not just commits, so treat a total that includes it as an upper bound.
    """
    start_year = int(created_at[:4])
    this_year = datetime.date.today().year
    years = range(start_year, this_year + 1)

    aliases = "\n".join(
        f'    y{y}: contributionsCollection('
        f'from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{{CONTRIB_FIELDS}}}'
        for y in years
    )
    year_ago = (datetime.date.today() - datetime.timedelta(days=365)).isoformat()
    query = (
        "query($login: String!) {\n  user(login: $login) {\n"
        f'    trailing: contributionsCollection('
        f'from: "{year_ago}T00:00:00Z", to: "{datetime.date.today().isoformat()}T23:59:59Z")'
        f" {{{CONTRIB_FIELDS}}}\n"
        f"{aliases}\n  }}\n}}"
    )

    data = client.query(query, {"login": login})
    user = (data or {}).get("user") or {}

    def totals(node: dict) -> tuple[int, int, int]:
        if not node:
            return 0, 0, 0
        return (
            node["totalCommitContributions"],
            node["restrictedContributionsCount"],
            node["contributionCalendar"]["totalContributions"],
        )

    public = private = calendar = 0
    for y in years:
        p, r, c = totals(user.get(f"y{y}"))
        public += p
        private += r
        calendar += c

    t_public, t_private, t_calendar = totals(user.get("trailing"))
    by_year = {}
    for y in years:
        p, r, _ = totals(user.get(f"y{y}"))
        by_year[y] = p + r

    return {
        "commits_public": public,
        "commits_private": private,
        "commits": public + private,
        "commits_year": t_public + t_private,
        "commits_ytd": by_year.get(this_year, 0),
        "commits_prev_year": by_year.get(this_year - 1, 0),
        "contributions": calendar,
        "contributions_year": t_calendar,
    }


SIGNAL_FIELDS = """
    pkg: object(expression: "HEAD:package.json") { ... on Blob { text } }
    root: object(expression: "HEAD:") { ... on Tree { entries { name } } }
"""


def fetch_repo_signals(client: Client, repos: list[dict], batch: int = 20) -> list[set[str]]:
    """Read each repository's manifest and root listing, aliased into batches."""
    from .techstack import signals_for_repo

    out: list[set[str]] = []
    for start in range(0, len(repos), batch):
        chunk = repos[start : start + batch]
        aliases = []
        for i, repo in enumerate(chunk):
            owner, name = repo["nameWithOwner"].split("/", 1)
            aliases.append(
                f'  r{i}: repository(owner: "{owner}", name: "{name}") {{{SIGNAL_FIELDS}}}'
            )
        data = client.query("query {\n" + "\n".join(aliases) + "\n}") or {}
        for i in range(len(chunk)):
            node = data.get(f"r{i}") or {}
            pkg = (node.get("pkg") or {}).get("text")
            entries = [e["name"] for e in (node.get("root") or {}).get("entries", [])]
            out.append(signals_for_repo(pkg, entries))
    return out


HOURS_FIELDS = """
    defaultBranchRef { target { ... on Commit {
      history(first: %d, author: {id: $authorId}) { nodes { authoredDate } } } } }
"""


def _local_hour(stamp: str, tz, offset: int) -> int:
    """UTC ISO timestamp -> local hour.

    Prefers a real time zone, which gets daylight saving right across a year of
    commits.  A fixed offset is the fallback: correct today, an hour out for the
    half of the year on the other side of the DST boundary.
    """
    if tz is not None:
        moment = datetime.datetime(
            int(stamp[0:4]), int(stamp[5:7]), int(stamp[8:10]),
            int(stamp[11:13]), int(stamp[14:16]),
            tzinfo=datetime.timezone.utc,
        )
        return moment.astimezone(tz).hour
    return (int(stamp[11:13]) + offset) % 24


def load_timezone(name: str | None):
    """Return a tzinfo for ``name``, or None if it cannot be resolved.

    zoneinfo landed in Python 3.9. Returning None lets the caller fall back to a
    fixed offset rather than failing the build on an older interpreter.
    """
    if not name:
        return None
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except Exception:
        return None


def commit_hours(
    client: Client,
    repos: list[dict],
    author_id: str,
    per_repo: int = 100,
    tz=None,
    offset: int = 0,
) -> dict[int, int]:
    """Histogram of local hours over a sample of recent commits.

    A sample, not a census: a full history walk is the expensive operation this
    project deliberately avoids.  Taking the most recent commits from the most
    recently pushed repositories is enough to show when someone works.
    """
    aliases = []
    for i, repo in enumerate(repos):
        owner, name = repo["nameWithOwner"].split("/", 1)
        aliases.append(
            f'  r{i}: repository(owner: "{owner}", name: "{name}") '
            f"{{{HOURS_FIELDS % per_repo}}}"
        )
    if not aliases:
        return {}
    query = "query($authorId: ID!) {\n" + "\n".join(aliases) + "\n}"
    data = client.query(query, {"authorId": author_id}) or {}

    hours: dict[int, int] = {}
    for i in range(len(repos)):
        ref = (data.get(f"r{i}") or {}).get("defaultBranchRef")
        if not ref:
            continue
        for node in ref["target"]["history"]["nodes"]:
            hour = _local_hour(node["authoredDate"], tz, offset)
            hours[hour] = hours.get(hour, 0) + 1
    return hours


def weekday_totals(calendar: dict) -> dict[str, int]:
    """Contributions summed by day of the week."""
    names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    totals = {n: 0 for n in names}
    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            date = datetime.date.fromisoformat(day["date"])
            totals[names[date.weekday()]] += day["contributionCount"]
    return totals


def collect_profile(client: Client, login: str, affiliations: list[str]) -> dict:
    """One query (plus a page each per extra 100 repos) for everything cheap.

    Deliberately excludes lines of code, which needs a full commit walk of every
    repository and is orders of magnitude more expensive than all of this
    combined.  See ``repo_loc`` and ``github.count_lines`` in config.yml.
    """
    today = datetime.date.today()
    variables = {
        "login": login,
        "from": f"{today - datetime.timedelta(days=365)}T00:00:00Z",
        "to": f"{today}T23:59:59Z",
        "affiliations": affiliations,
        "cursor": None,
    }

    data = client.query(PROFILE_QUERY, variables)
    user = (data or {}).get("user")
    if not user:
        raise GitHubError(f"No such GitHub user: {login!r}")

    repos = list(user["repositories"]["nodes"])
    page = user["repositories"]["pageInfo"]
    while page["hasNextPage"]:
        variables["cursor"] = page["endCursor"]
        more = client.query(PROFILE_QUERY, variables)
        node = more["user"]["repositories"]
        repos.extend(node["nodes"])
        page = node["pageInfo"]

    return {
        "id": user["id"],
        "created_at": user["createdAt"],
        "repo_nodes": repos,
        "calendar_raw": user["contributionsCollection"]["contributionCalendar"],
        "followers": user["followers"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "prs_merged": user["prsMerged"]["totalCount"],
        "prs_open": user["prsOpen"]["totalCount"],
        "issues_opened": user["issues"]["totalCount"],
        "repos": user["repositories"]["totalCount"],
        "stars": sum(r["stargazerCount"] for r in repos),
        "calendar": read_calendar(user["contributionsCollection"]["contributionCalendar"]),
        "languages": top_languages(repos),
    }


def token_from_env() -> str:
    """ACCESS_TOKEN is what the workflow sets; GITHUB_TOKEN is the local default."""
    for name in ("ACCESS_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(name):
            return os.environ[name]
    return ""
