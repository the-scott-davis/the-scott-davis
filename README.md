<!-- ─────────────────────────────────────────────────────────────────────────
     This is a GitHub profile README. For it to appear on the profile page the
     repository must be named exactly the same as the GitHub username.
     Everything below the card is collapsed so the profile itself stays clean.
     ───────────────────────────────────────────────────────────────────────── -->

<a href="https://github.com/the-scott-davis/the-scott-davis">
  <picture>
    <source media="(prefers-color-scheme: dark)"
            srcset="https://raw.githubusercontent.com/the-scott-davis/the-scott-davis/main/dist/dark_mode.svg">
    <img alt="Scott Davis — GitHub profile card"
         src="https://raw.githubusercontent.com/the-scott-davis/the-scott-davis/main/dist/light_mode.svg">
  </picture>
</a>

<details>
<summary><b>How this card is built — and how to make your own</b></summary>

<br>

The card is an SVG generated from [`config.yml`](config.yml) and a source image.
Nothing about it is hand-drawn: the ASCII portrait comes out of an image
converter, the stats come from GitHub's GraphQL API, and the layout — column
alignment, dot leaders, canvas size — is computed from whatever is in the config
file. Add a row, delete a row, reorder the list, change the colours; the SVG
resizes itself.

There are two portrait modes. `ascii` renders characters, and suits logos and
other high-contrast art. `pixel` quantises an image to a small palette and emits
one `<path>` per colour, and suits photographs. Which one your art wants comes
down to its *luminance* contrast, since characters have no colour to work with —
[the docs explain how to check](docs/CUSTOMIZING.md#choosing-between-them).

### Fork it

```bash
git clone https://github.com/the-scott-davis/the-scott-davis.git my-profile
cd my-profile
make install
```

1. **Rename the repository to your GitHub username.** That is what makes it a
   profile README.
2. **Point `portrait.source` at your own art** and run `make portrait`. Start by
   [picking a mode](docs/CUSTOMIZING.md#choosing-between-them) — a logo wants
   `ascii`, a photo wants `pixel`. `make analyze` will tell you which. If you
   want an ASCII portrait of a *person*, read
   [docs/PORTRAIT-PHOTOS.md](docs/PORTRAIT-PHOTOS.md) before you shoot — the
   photo you need is not a good headshot, and the difference is not obvious.
3. **Edit `config.yml`.** Set `github.username`, then rewrite the `fields:`
   list to say whatever you want it to say.
4. **Preview without a token:** `make build`. This renders from cached numbers,
   so you can iterate on layout offline.
5. **Add a token and go live.** Create a **classic** personal access token with
   the `repo` scope, save it as a repository secret named `ACCESS_TOKEN`, then
   run the **Build profile card** workflow. It re-runs daily.

   The `repo` scope matters: commit counts come from GitHub's contributions API,
   and the private-contribution portion reads 0 without it. A fine-grained token
   limited to Contents+Metadata will silently undercount anyone whose work is
   mostly in private repositories.

### Commands

| | |
|---|---|
| `make portrait` | Regenerate the portrait from the photo |
| `make preview` | Render the portrait to a scratch file, write nothing committed |
| `make build` | Render the cards from cached stats — no token needed |
| `make fetch` | Fetch fresh stats from GitHub and render |
| `make check` | Validate `config.yml` |
| `make test` | Run the tests |

### Working on it with an AI agent

[`AGENTS.md`](AGENTS.md) describes the layout, the data flow, and the rules that
are easy to get wrong. Claude Code, Cursor, and anything else that reads
`AGENTS.md` or `CLAUDE.md` will pick it up automatically.

### Credit

The neofetch-style-portrait-plus-stats idea comes from
[Andrew6rant/Andrew6rant](https://github.com/Andrew6rant/Andrew6rant). This is
an independent implementation — no code is shared with it — built to be
configurable rather than hand-edited. MIT licensed.

</details>
