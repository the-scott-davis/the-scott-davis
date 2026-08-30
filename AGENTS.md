# AGENTS.md

Guidance for AI agents working in this repository. Humans: `README.md` is the
faster read; `docs/CUSTOMIZING.md` is the full config reference.

## What this is

A GitHub profile README that renders as a neofetch-style card: an ASCII
portrait on the left, a list of key/value rows on the right. Both SVGs (`dist/dark_mode.svg`,
`dist/light_mode.svg`) are **generated artifacts**. They are committed because
GitHub serves them over `raw.githubusercontent.com`, but they are never edited
by hand.

**The single source of truth is `config.yml`.** If a change can be expressed
there, express it there.

## Data flow

```
assets/logo.png ───[profilecard.portrait]──> assets/portrait.txt ─┐
                                                                  ├──[profilecard.render]──> dist/*.svg
config.yml ───────────────────────────────────────────────────────┤
GitHub GraphQL ──[profilecard.github]──> cache/loc.json ──[stats]─┘
```

The portrait file is a *committed intermediate*. In `ascii` mode it is a text
file dropped into `<tspan>`s; in `pixel` mode it is a small PNG that `render.py`
run-length encodes into one `<path>` per colour. Either way the card stays a
self-contained SVG with no linked or embedded image.

## Layout

| Path | What it does |
|---|---|
| `config.yml` | Every user-facing choice: identity, rows, colours, portrait tuning |
| `profilecard/config.py` | Parses and validates the above into dataclasses |
| `profilecard/analyze.py` | Diagnostic: will this source survive ASCII? (`make analyze`) |
| `profilecard/techstack.py` | Dependency and marker-file signatures → detected technologies |
| `profilecard/ascii_art.py` | Art → characters. The default `mode: ascii` |
| `profilecard/pixel_art.py` | Art → pixel-art PNG, and PNG → rectangles. `mode: pixel` |
| `profilecard/portrait.py` | CLI for the converter (`python -m profilecard.portrait`) |
| `profilecard/github.py` | GraphQL client, retries, and the raw queries |
| `profilecard/cache.py` | Per-repo line-count cache, keyed on the branch head SHA |
| `profilecard/stats.py` | Orchestrates collection; builds the placeholder dict |
| `profilecard/render.py` | Computes layout and emits the SVG |
| `profilecard/__main__.py` | CLI entry point (`python -m profilecard`) |
| `scripts/nightly.sh` | The scheduled rebuild. Reads the token from the keyring at use |
| `dist/` | Generated. Committed. Never hand-edit |
| `cache/loc.json` | Generated. Committed. Safe to delete; it rebuilds |

## Rules that are easy to get wrong

1. **Never hand-edit `dist/*.svg`.** Change `config.yml` and run `make build`.
   A hand edit is silently destroyed by the next scheduled workflow run.

2. **Never hardcode a value that belongs in `config.yml`.** Adding a row to the
   card means adding an entry to `card.fields`, not a line to `render.py`. New
   dynamic data means a new key in the dict returned by `stats.to_values()`,
   which makes it available as `{placeholder}` everywhere.

3. **Never report a "stack" from GitHub's language statistics alone.** They
   measure bytes and have no sense of time, so one large legacy repository
   outranks everything current. This account read as 66% C# for someone who had
   written nothing but TypeScript in two years. `stack.since_years` handles the
   time blindness and `stack.exclude_languages` the rest. Separately, the
   languages API cannot see a framework, cloud, or database at all; `{tech}`
   comes from `profilecard/techstack.py`, which reads dependency manifests and
   marker files and ranks by how many repositories use each thing.

4. **The contribution grid is already paid for.** `- heatmap: contributions`
   draws `Stats.calendar`, which is the same `contributionCalendar` response
   the streak, active-day, and busiest-day figures are read out of. Do not add
   a query for it. It includes private activity, which is exactly why it agrees
   with the commit totals in rule 6 while a repository walk would not.

5. **Stats have two cost tiers, and the cheap one is nearly everything.**
   `stats.collect()` gets commits, pull requests, streaks, and languages in two
   API calls and about five seconds. `_collect_lines()` walks every commit of
   every repository and is gated behind `github.count_lines`, off by default.
   Do not move work from the first into the second, and do not turn line
   counting on by default because a card looks sparse.

6. **Commit counts never come from walking repositories.** They come from
   `contributionsCollection`. A walk sees only default branches of repositories
   the token can read, which for an account whose work is private undercounts by
   orders of magnitude: this account walks to roughly 0 against a true 17,000.
   Private activity arrives as one opaque aggregate, `restrictedContributionsCount`,
   which needs a classic token with `repo` scope; a fine-grained Contents+Metadata
   token silently returns zero for it.

7. **`make build` is the offline path.** It renders from `cache/loc.json` and
   needs no token, so use it for any layout or config work. Only `make fetch`
   talks to the API, and it needs `GITHUB_TOKEN` or `ACCESS_TOKEN` in the
   environment. Do not reach for the network to verify a layout change.

8. **Layout is computed, not measured.** `render.py` reserves
   `card.char_width` pixels per character and assumes a monospace font. Any
   change to the font stack has to be matched by a change to `char_width`, or
   the text will clip. There is one spare column of slack, not more.

9. **The portrait's dimensions drive the card's height**, when there is one.
   A taller portrait makes a taller card. `assets/portrait.txt` is generated, so
   regenerate it with `make portrait` rather than editing the characters. With
   `card.show_portrait: false` the portrait is not read at all, the card's
   height comes from its tallest text column instead, and `card.columns`
   defaults to 2 because a lone column of rows against a full-width README is
   mostly empty space. Columns split on `separator` boundaries, whole sections
   at a time, minimising the tallest column; `- column_break: true` overrides
   that and is ignored in a one-column card. A `- heading:` field opens a
   section the way a separator does, so the two are never written together.
   `- heatmap: contributions` is a block rather than a row: it claims several
   rows and widens its column, and both numbers are computed from
   `card.heat_cell`/`heat_gap` so the splitter can measure it before any data
   is fetched.

10. **The portrait mode is chosen by file extension, not a flag.** `render.py`
   sees `.png` and draws rectangles; it sees `.txt` and draws characters. A
   theme is therefore self-describing. `portrait.mode` only controls what
   `make portrait` *writes*.

11. **Pick the mode from the source art's LUMINANCE contrast, not its subject.**
   Characters carry tone only, so anything that separates by colour but not by
   brightness disappears. The photograph originally used here measured 2 levels
   of luminance difference (out of 255) between face and shirt, against 99 in
   which is why every ASCII attempt produced a blob, at any column count. The
   logo separates by ~215 levels, so it renders crisply. Before concluding that
   an ASCII portrait needs more columns or a better ramp, **measure the source**
   with `make analyze`: more cells cannot invent an edge that is not in the data.
   `mode: pixel` is the answer for photographs, and it is fully supported.

12. **An ASCII portrait is set at its own font size** (`card.portrait_font_size`
   and friends). It is texture, not text, so it is not held to a readable size.
   Shrinking it is what buys the column count detail depends on. Changing it
   without matching `portrait_char_width` will skew the layout.

13. **The RLE in `pixel_art.load_boxes` must stay lossless.** It exists purely to
   keep the SVG small, and `tests/test_pixel_art.py` asserts that replaying the
   boxes reproduces the source image exactly. Keep that test passing.

14. **Unknown placeholders are an error, not a blank.** `{typo}` raises a
   `ConfigError` naming the available keys. Keep it that way: a card that
   silently renders `{discrod}` is worse than one that fails the build.

## Docs

`README.md` is the fork guide, `docs/CUSTOMIZING.md` is the config reference,
and `docs/PORTRAIT-PHOTOS.md` covers shooting a photo that survives ASCII. Send
people to the last one rather than re-deriving the advice. It is grounded in
measurements taken from real failures, not general photography lore.

## Security posture

The card is built on the owner's machine and pushed, not built in CI. That is
why no workflow here handles a secret, and why none has a `pull_request`
trigger: in a public repository that would let a stranger run CI on their own
code. Nothing could be read or written even so, but the property worth keeping
is simpler than the argument for why it would be safe.

If you are tempted to move the build into Actions, understand what it costs: a
classic PAT with `repo` scope, meaning read and write to every repository the
owner has, stored indefinitely as a repository secret. The current design needs
stored credential at all. Do not trade that away for a green checkmark.

Never commit `cache/loc.json` with plaintext repository names; keys are hashed
because this repository is public and the accounts this project suits are the
ones whose repository names are not.

## Verifying a change

```bash
make check    # config parses
make build    # SVGs regenerate from cache
make test     # unit tests
```

To look at the result, open `dist/dark_mode.svg` in a browser. Do not trust
macOS Quick Look (`qlmanage`) for this. It substitutes fonts and misreports
the layout. A browser is what GitHub uses, so a browser is the check that counts.

## Conventions

- Python 3.10+, standard library plus the four packages in `requirements.txt`.
- Type hints on public functions; `from __future__ import annotations` at the top.
- Errors that a user can fix are `ConfigError` with the offending key in the
  message. Errors from the API are `GitHubError` with the reason, not the status code.
- Comments explain *why*, not *what*. The existing files set the density.
