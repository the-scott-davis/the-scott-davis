"""``python -m profilecard`` -- build the card SVGs.

    python -m profilecard --offline    # render layout from cache, no token needed
    python -m profilecard              # fetch fresh stats and render
    python -m profilecard --check      # validate config.yml and exit
"""

from __future__ import annotations

import argparse
import sys
import time

from .config import Config, ConfigError
from .github import Client, GitHubError, token_from_env
from .render import render_all
from .stats import collect, offline_stats, to_values


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m profilecard", description=__doc__)
    p.add_argument("-c", "--config", default="config.yml")
    p.add_argument(
        "--offline",
        action="store_true",
        help="skip the GitHub API and render from the cached numbers "
        "(how you preview layout changes without a token)",
    )
    p.add_argument("--check", action="store_true", help="validate config.yml and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start = time.perf_counter()

    try:
        cfg = Config.load(args.config)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    if args.check:
        print(f"{cfg.path}: ok, {len(cfg.card.fields)} fields, "
              f"{len(cfg.themes)} theme(s): {', '.join(t.name for t in cfg.themes)}")
        return 0

    github_name = None
    if args.offline:
        stats = offline_stats(cfg)
        print("offline: rendering from cache, stats may be stale")
    else:
        try:
            client = Client(token_from_env(), verbose=args.verbose)
            stats = collect(cfg, client, verbose=args.verbose)
        except GitHubError as exc:
            print(f"github error: {exc}", file=sys.stderr)
            return 1

    try:
        values = to_values(cfg, stats, github_name)
        written = render_all(cfg, values, stats.calendar)
    except ConfigError as exc:
        print(f"config error: {exc}", file=sys.stderr)
        return 2

    for path in written:
        print(f"wrote {path}")

    if not args.offline:
        print(
            f"{stats.api_calls} API calls, "
            f"{stats.cache_hits} cached / {stats.cache_misses} walked, "
            f"{time.perf_counter() - start:.1f}s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
