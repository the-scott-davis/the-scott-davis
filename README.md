<!-- ─────────────────────────────────────────────────────────────────────────
     This is a GitHub profile README. For it to appear on the profile page the
     repository must be named exactly the same as the GitHub username.
     Everything below the card is collapsed so the profile itself stays clean.
     ───────────────────────────────────────────────────────────────────────── -->

<a href="https://github.com/the-scott-davis/the-scott-davis">
  <picture>
    <source media="(prefers-color-scheme: dark)"
            srcset="https://raw.githubusercontent.com/the-scott-davis/the-scott-davis/main/dist/dark_mode.svg">
    <img alt="Scott Davis, GitHub profile card"
         src="https://raw.githubusercontent.com/the-scott-davis/the-scott-davis/main/dist/light_mode.svg">
  </picture>
</a>

<details>
<summary><b>How this card is built, and how to make your own</b></summary>

<br>

Everything on the card is generated. The numbers come from GitHub's GraphQL API,
the layout is computed from [`config.yml`](config.yml), and a Python script
writes the SVG. Add a row, delete one, reorder them, change the colours: the
card resizes itself. Nothing is hand-edited.

Most of the work went into three decisions that are not obvious from looking at
it, so they are worth calling out.

**The stack is read from dependency files, not from GitHub's language bar.**
That bar measures bytes and has no sense of time, so one large old repository
can outrank everything you have written this year. This account read as 66% C#
for someone who had shipped nothing but TypeScript in two years. The card cuts
by push date first, then detects frameworks, clouds and databases from the
manifests that name them, which the languages API cannot see at all.

**Commit counts come from the contributions API**, the same source as the graph
on your profile, so private work is counted. Walking repositories instead would
miss nearly all of it: a walk only sees default branches it has access to, which
for this account is close to nothing.

**The contribution grid at the bottom is free.** It is drawn from the same
response the streak and active-day figures are read out of, so it costs no
extra API call and cannot disagree with them.

There is no portrait on this card, because the same artwork is already the
avatar sitting right next to it. Switching it off hands the full width to the
rows, which then run in two balanced columns instead of one tall one. If you do
want a portrait, there are two modes. `ascii` draws characters and suits logos
and other high-contrast art. `pixel` quantises to a small palette and suits
photographs. Which one your image wants comes down to its *luminance* contrast,
since characters have no colour to work with, and
[the docs explain how to check](docs/CUSTOMIZING.md#choosing-between-them).

### Fork it

```bash
git clone https://github.com/the-scott-davis/the-scott-davis.git my-profile
cd my-profile
make install
```

1. **Rename the repository to your GitHub username.** That is what makes it a
   profile README.
2. **Decide whether you want a portrait.** If you do not, set
   `card.show_portrait: false` and skip to the next step. If you do, point
   `portrait.source` at your art and run `make portrait`. Run `make analyze`
   first and it will tell you which mode suits the image: logos want `ascii`,
   photographs want `pixel`. If you are set on an ASCII portrait of a *person*,
   read [docs/PORTRAIT-PHOTOS.md](docs/PORTRAIT-PHOTOS.md) before you shoot.
   The photo you need is not a good headshot, and the difference is not obvious
   until you have wasted an afternoon on it.
3. **Edit `config.yml`.** Set `github.username`, then rewrite the `fields:`
   list to say whatever you want it to say. Sections come from `heading`, and
   the columns balance themselves around them.
4. **Preview without a token:** `make build`. This renders from cached numbers,
   so you can work on the layout offline and check it in a browser.
5. **Schedule it.** Run `make venv`, then `./scripts/nightly.sh` once by hand to
   prove it works, then point your scheduler at that script.
   [docs/PUBLISHING.md](docs/PUBLISHING.md) covers the options.

   The card is rebuilt on your own machine rather than in CI, so there is no
   personal access token to create and no secret for GitHub to hold. The `gh`
   CLI you are already signed in to supplies a token from the system keyring at
   the moment of use. Consequently no workflow in this repository touches a
   secret, and none can be triggered by anyone without write access.

### Commands

| | |
|---|---|
| `make portrait` | Regenerate the portrait from the photo |
| `make preview` | Render the portrait to a scratch file, write nothing committed |
| `make build` | Render the cards and banner from cached stats, no token needed |
| `make fetch` | Fetch fresh stats and render the cards and banner |
| `make venv` | Build the virtualenv the scheduled job runs from |
| `make nightly` | Run the scheduled rebuild by hand |
| `make check` | Validate `config.yml` |
| `make test` | Run the tests |
| `/linkedin-banner` | Validate the banner and hand it over to upload (Claude Code skill) |

### The LinkedIn banner

`banner:` in `config.yml` builds a 1584x396 cover photo from the same numbers,
written to `dist/linkedin_banner.png` on every fetch. Upload the PNG, not the
SVG -- LinkedIn does not accept SVG.

It is not simply the card at a different size, because a profile page does two
things to it. The app crops to roughly the middle 60% of the width, so the
block is centred and no wider than `safe_width`. And your profile photo covers
the bottom-left corner, which is why the short section sits in the left column
and the long ones are stacked on the right: the left column stops above the
photo, and the photo fills the gap. Both properties are checked on every
render, and a change that breaks one prints a warning saying by how much.

There is no LinkedIn API for a member's cover photo, so the upload is manual.
The `/linkedin-banner` skill in this repo does everything either side of it:
checks the file is the right size and actually current, shows it to you, hands
over a clickable path, and remembers what you last uploaded so it can tell you
when re-uploading is not worth the bother.

Upload it after a `make fetch`, not a `make build`. `make build` has no commit
counts to replay offline, so it writes a banner full of zeros -- fine for
checking a layout, not for your profile.

### Working on it with an AI agent

[`AGENTS.md`](AGENTS.md) describes the layout, the data flow, and the rules that
are easy to get wrong. Claude Code, Cursor, and anything else that reads
`AGENTS.md` or `CLAUDE.md` will pick it up automatically.

### Credit

The neofetch-style-portrait-plus-stats idea comes from
[Andrew6rant/Andrew6rant](https://github.com/Andrew6rant/Andrew6rant). This is
an independent implementation, built to be configurable rather than
hand-edited. No code is shared with it. MIT licensed.

</details>
