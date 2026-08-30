# Customizing the card

Everything lives in [`config.yml`](../config.yml). After any edit:

```bash
make build
```

That renders from cached stats and needs no GitHub token, so you can iterate
freely. Open `dist/dark_mode.svg` in a browser to look at the result.

---

## Rows

`card.fields` is an ordered list. Each entry is one row.

```yaml
card:
  fields:
    - label: OS
      value: macOS, Linux
```

**To remove a row, delete it.** Every row below shifts up, the dot leaders
re-align, and the SVG gets shorter. Nothing else needs touching. To keep a row
around but hide it, set `enabled: false`:

```yaml
    - label: Contact.Discord
      value: "yourhandle"
      enabled: false        # keeps the line in the file, off the card
```

A dot in the label renders as a nested key, the way neofetch groups things:

```yaml
    - label: Languages.Programming     # -> Languages.Programming: ...
```

A section title, set flush left with a rule running from the end of the text to
the edge of its column:

```yaml
    - heading: Stack
```

A heading opens its own section, which is what puts the blank line above it, so
it is written *instead of* a `separator`, not next to one. The rows under a
heading should drop the prefix they would otherwise carry: with a `Commits`
heading above them, `Commits.Per day` is just `Per day`.

Your contribution grid, drawn as squares rather than text:

```yaml
    - heading: Last 365 days
    - heatmap: contributions
```

This costs no extra API call. The day grid is the same response the streak and
active-day numbers are already read out of. It is a block, not a row: it claims
as many rows as it needs and widens its column to fit, so the column splitter
balances around it. Offline (`make build`) it renders at full size in the
quietest shade, so the layout is the real one even without a token.

A blank spacer line, for a section with no title:

```yaml
    - separator: true
```

And, in a two-column card, an explicit place for the second column to start:

```yaml
    - column_break: true
```

See [Turning the portrait off](#turning-the-portrait-off). In a one-column card
it does nothing at all.

### Placeholders

Any `{name}` in a `value` (or in `card.title`, or in a label) is substituted.

**Identity**

| Placeholder | Source |
|---|---|
| `{username}` | `github.username` |
| `{name}` | `vars.name`, falling back to the GitHub display name |
| `{age}` | Computed from `vars.birthday` |
| `{today}` `{year}` `{prev_year}` | Today's date, this year, last year |
| `{github_since}` | Year the GitHub account was created |
| anything under `vars:` | Yours |

**Commits**, from the contributions API, the same source as your profile graph.
Includes private activity, so these are the real numbers even if your work is not
public.

| Placeholder | Meaning |
|---|---|
| `{commits}` | All time |
| `{commits_ytd}` | This calendar year so far |
| `{commits_prev_year}` | Last calendar year |
| `{commits_year}` | Trailing 365 days |
| `{commits_public}` `{commits_private}` | The split |
| `{contributions}` `{contributions_year}` | All contribution types, not just commits |

**Cadence**, derived from the day-by-day contribution grid.

| Placeholder | Meaning |
|---|---|
| `{per_day}` | Average per calendar day over the trailing year |
| `{per_active_day}` | Average across days you actually committed |
| `{active_days}` `{calendar_days}` `{active_pct}` | 293, 365, and 80 |
| `{current_streak}` `{longest_streak}` | Consecutive active days |
| `{busiest_count}` `{busiest_date}` | Your single biggest day |

**Output**

| Placeholder | Meaning |
|---|---|
| `{prs_merged}` `{prs_open}` | Pull requests |
| `{issues_opened}` | Issues you opened |
| `{repos}` | Non-fork repositories you own |
| `{contributed}` | Repositories you have contributed to |
| `{followers}` `{stars}` | |

**Stack**. See [What you build with](#what-you-build-with) for how these are
derived and why the defaults filter so aggressively.

| Placeholder | Meaning |
|---|---|
| `{tech}` | Every detected technology, most widely used first |
| `{tech_3}` `{tech_4}` `{tech_5}` `{tech_6}` | Just the top N |
| `{tech_top}` | The single most widely used |
| `{language_top}` `{language_top_pct}` | Leading language and its share |
| `{languages}` | Top 4 with percentages |
| `{languages_list}` | Names only, **excluding** the leader, so it pairs with `{language_top}` |
| `{languages_all}` | Every language, largest first |
| `{recent_repos}` | Repositories inside the `since_years` window |

**Rhythm**, meaning when you work.

| Placeholder | Meaning |
|---|---|
| `{busiest_weekday}` `{quietest_weekday}` | By contribution volume |
| `{busiest_weekday_count}` | Contributions on that weekday |
| `{weekend_pct}` | Share of contributions falling on Sat/Sun |
| `{busiest_hour}` `{busiest_hour_pct}` | Peak single hour, local time |
| `{busiest_window}` | Peak two-hour window, local time |
| `{github_age}` | How long the account has existed |

**Lines of code**, only populated when `github.count_lines` is on (see below).

| Placeholder | Meaning |
|---|---|
| `{loc}` `{loc_added}` `{loc_deleted}` | Net, added, deleted |

Numbers arrive pre-formatted with thousands separators. Add your own by adding
a key to `vars:` and it becomes a placeholder automatically:

```yaml
vars:
  timezone: America/New_York

card:
  fields:
    - label: Timezone
      value: "{timezone}"
```

A misspelled placeholder fails the build and tells you the valid names. That is
deliberate: a card that renders `{discrod}` to the world is worse than one that
refuses to build.

For a literal brace, double it: `{{` and `}}`.

### Inline colour

Five tags, all drawing their colour from the active theme:

```yaml
    - label: GitHub.Lines of Code
      value: "{loc} <dim>(</dim><add>{loc_added}++</add><dim>,</dim> <del>{loc_deleted}--</del><dim>)</dim>"
```

`<key>` `<value>` `<dim>` `<add>` `<del>`. They cannot nest.

---

## Themes

Each entry under `themes:` produces one SVG. The shipped config has `dark` and
`light`, which is what the `<picture>` element in `README.md` switches between.

```yaml
themes:
  dark:
    output: dist/dark_mode.svg
    portrait: assets/portrait.txt
    bg: "#161b22"      # card background
    fg: "#c9d1d9"      # default text and the portrait
    key: "#ffa657"     # row labels
    value: "#a5d6ff"   # <value> spans
    dim: "#6e7681"     # dot leaders, punctuation, <dim> spans
    add: "#3fb950"
    delete: "#f85149"
    rule: "#30363d"    # the line under the title, and beside each heading
    heading: "#e6edf3" # section titles
    heat: ["#21262d", "#4d2a08", "#8a4a0d", "#cc7a1f", "#ffa657"]
```

`heat` is the contribution grid's five shades, quietest first. Omit it and a
ramp is blended from `bg` up to `key`, which is fine for most palettes, but
check it against your own activity before trusting it. Shading is on a square
root scale, because one outlier day (a 84-commit day here) flattens every
ordinary week into the quietest shade on a linear one. If most of your days are
active, the ramp needs real separation between steps or the year reads as one
flat block; that is why the shipped values are hand-picked rather than blended.
Orange in particular desaturates to brown at low luminance, where a blue ramp
would hold up better.

Only `output`, `bg`, and `fg` are required; the rest fall back to `fg`.
`portrait` joins them whenever `card.show_portrait` is on, which it is by
default. Add a third theme if you want one. Nothing stops you, though the
README only references two.

---

## Turning the portrait off

If the art is already your GitHub avatar, the profile page shows it twice, side
by side. One line fixes that:

```yaml
card:
  show_portrait: false
```

The whole card width then goes to the rows, so the layout switches to two
columns, because a single tall column of nineteen rows against a full-width README is
mostly empty space. Override the count if you want something else:

```yaml
card:
  columns: 2           # default: 1 with a portrait, 2 without
  column_gutter: 4     # blank columns between them
```

Columns are split on the section boundaries (every `heading` and every
`separator` starts one), whole sections at a time, at whichever boundary makes
the tallest column shortest. The card is as tall as
its tallest column, so that is the thing worth minimising. Sections are never
cut in half automatically, which is not always what you want: one section of ten
rows out of nineteen has no good boundary near the middle, and the right column
ends up half empty. Put the break where you want it instead:

```yaml
    - label: Commits.Active days
      value: "..."

    - column_break: true      # the second column starts here

    - label: Commits.Record
      value: "..."
```

An explicit break wins over the automatic split, and every break is ignored when
the card is one column, so leaving one in the file costs nothing if you turn
the portrait back on.

With the portrait off, nothing reads `themes.<name>.portrait` and
`assets/portrait.txt` stops mattering. Leave both alone and `show_portrait: true`
brings the old card straight back.

---

## Tuning the portrait

`make portrait` reads the `portrait:` block and writes the portrait file. Every
option maps to a flag, so the fast loop is to preview with flags and then write
the numbers you liked back into `config.yml`:

```bash
make preview                                              # current settings
python -m profilecard.portrait --preview --width 80 --palette 48
```

In pixel mode `--preview` writes `portrait-preview.png` at 6x nearest-neighbour
so you can actually see it. That file is gitignored.

### Two modes

```yaml
portrait:
  mode: ascii     # or: pixel
```

**`ascii`** writes a block of monospace characters. **`pixel`** downsamples to a
limited palette and writes a small PNG, which the renderer turns into one
`<path>` per colour. Either way the card stays a self-contained SVG.

The renderer picks its behaviour from the file extension in
`themes.<name>.portrait`: `.txt` means characters, `.png` means pixels, so a
theme is self-describing and the two can coexist.

### Choosing between them

Don't guess. Measure:

```bash
python -m profilecard.portrait --analyze your-shot.jpg
```

Characters carry tone and nothing else, so anything that separates by colour but
not by brightness simply disappears in ASCII, and no amount of extra columns
brings it back. The tool reports **edge strength**, the mean of the strongest 5%
of brightness steps inside the subject, and needs 130+ out of 255 for ASCII.

It also reports source pixels per character cell. Resolution is almost never the
constraint: at 72 columns you need roughly 3 px per cell, and any modern camera
gives you several times that. If a portrait looks soft, the fix is lighting.

The photograph this project started with scores **93**. Its subject's face and
shirt sit 2 levels apart out of 255 in brightness. They are 99 apart in colour
and all but identical in grey, so every ASCII rendering came out a blob, at 45 columns and
still at 120. The palm logo scores **151** and renders cleanly.

Shooting specifically for an ASCII portrait is its own skill, and the photo you
want is emphatically not a good headshot. Soft flattering light erases exactly
the structure characters need. [PORTRAIT-PHOTOS.md](PORTRAIT-PHOTOS.md) covers
it: lighting setups, what to wear, what to avoid, and a ten-second test you can
run on your phone before you bother transferring the file.

| Source | Use |
|---|---|
| Logo, icon, silhouette, line art, high-contrast graphic | `ascii` |
| Photograph, anything softly lit, anything where colour does the work | `pixel` |

To switch to a photograph, point `portrait.source` at it, set `mode: pixel`, and
point both themes at the `.png` output. `assets/photo.jpg` and a working pixel
configuration are kept in git history for reference.

### Pixel options

| Option | Effect |
|---|---|
| `width` | Art pixels across. Height follows the source aspect ratio unless you set `height` |
| `crop` | `[left, top, right, bottom]` as 0–1 fractions of the source |
| `palette` | Colours to quantise to. Fewer reads as flatter, more obviously "pixel art"; more preserves subtle shading |
| `dither` | Off by default. Dithering trades flat regions for perceived colour depth, which fights the look |
| `saturation` / `contrast` / `brightness` | Applied after downsampling, before quantising |
| `sharpen` | Unsharp mask *before* downsampling. Useful on a soft or slightly out-of-focus source |

Two card-geometry settings control how big it lands on the card:

```yaml
card:
  pixel_size: 6         # SVG pixels per art pixel, 64 x 6 = a 384px-wide portrait
  portrait_radius: 6    # rounded corners, 0 for square
```

`width` and `pixel_size` are independent, and they trade off against each other.
Raising `width` adds detail and file size; raising `pixel_size` makes the same
art render larger and chunkier. Pick `width` for how recognisable you want it,
then `pixel_size` for how much room it should take next to the text.

### What actually matters

Crop first, and crop tight: head and shoulders. Everything else is secondary to
getting the face large in the frame.

Then check the file size: `dist/dark_mode.svg` is around 38 KB at the defaults.
It scales roughly with `width` squared, so 96 pixels wide is more than double
the bytes of 64. Somewhere past 96 you are shipping a photograph with extra
steps.

### ASCII options

Only relevant under `mode: ascii`.

| Option | Effect |
|---|---|
| `width` | Target columns |
| `ramp` | Character set, lightest to darkest. Named (below) or a literal string |
| `cell_aspect` | Character cell width / height. Must match `portrait_char_width / portrait_line_height` or the art comes out stretched |
| `sharpen` | Unsharp mask before downsampling. Essential for fine detail like palm fronds |
| `autocontrast` | Percent clipped off each end of the histogram |
| `gamma` | `>1` darkens midtones, `<1` brightens them |
| `black_point` / `white_point` | Manual levels, instead of `autocontrast` |
| `vignette` / `vignette_power` | Fades the corners, the main tool for making a busy background go away |
| `floor` | Anything darker than this becomes empty space |
| `invert` | For a light card, see below |
| `trim` | Drop blank rows and columns from the edges (default on) |

#### Ramps

| Name | Use |
|---|---|
| `silhouette` | `" .:-+*#%@"`, for logos and flat high-contrast art |
| `measured` | 24 levels, evenly spaced in *measured* ink coverage |
| `measured32` | the same, at 32 levels |
| `blocks` `shades` | block-drawing characters, chunky |
| `classic` `minimal` `dots` `detailed` | conventional hand-written ramps |

`measured` and `measured32` were built by rendering every printable ASCII
character in a monospace font, measuring what fraction of its cell each one
inks, and sampling that range at even intervals. Hand-written ramps tend to
bunch up in the midtones; these step evenly. They are baked in as constants
rather than measured at build time, so a fork does not need a font file.

For a near-binary source, pair `silhouette` with a narrow `black_point` /
`white_point` window. That acts as a soft threshold, sending the subject solid
and the background empty while letting only anti-aliased edges land in between.
That is how the shipped palm logo is configured.

#### Photographs in ASCII

A busy background is the hard case here, and `vignette` plus `floor` is how you
deal with it: the vignette pushes the corners down, the floor snaps whatever is
left of them to nothing. Work in order: crop, `sharpen`, contrast, then
background knockout last.

For a light card, reversing the ramp is **not** enough: you want dark ink where
the photo is dark, which turns the photo's dark background into a solid block.
An inverted variant needs a much harder background knockout. Per-output
overrides exist for exactly this:

```yaml
portrait:
  mode: ascii
  outputs:
    normal:
      path: assets/portrait.txt
    inverted:
      path: assets/portrait-light.txt
      invert: true
      floor: 0.34        # much higher than the normal variant
      ink_floor: 0.10
```

Pixel mode sidesteps the problem entirely, since colour reads on either background,
so both themes share one portrait file.

---

## Geometry

Rarely needed, but there if you want it:

```yaml
card:
  font_size: 16          # the field list
  line_height: 20
  char_width: 9.6        # reserved pixels per character
  portrait_font_size: 10 # the ascii portrait, independent of the text above
  portrait_line_height: 11
  portrait_char_width: 6.0
  padding: 18
  corner_radius: 14
  gutter: 4              # blank columns between portrait and rows
  column_gutter: 4       # blank columns between two field columns
  title_gap: 10          # extra pixels between the title and the first row
  heat_cell: 7           # side of one contribution square
  heat_gap: 2            # space between squares
  min_dots: 2            # shortest dot leader
```

`title_gap` is space, not a line. The rule under the title stays tucked under
the title's descenders; the gap is what pushes the first row clear of the pair.

The portrait has its own type metrics because it is texture, not something
anyone reads. Setting it smaller than the field text is what buys the column
count an ASCII portrait needs. The same card width holds 45 columns at 16px but
72 at 10px, and columns are the only source of detail characters have. Set
`portrait_font_size` alone and the leading scales with it; the `portrait_*`
values fall back to the field-text ones when omitted.

Keep `portrait.cell_aspect` equal to `portrait_char_width / portrait_line_height`
or the portrait will render stretched.

`char_width` must match the font stack. The default assumes the `~0.6em`
advance shared by DejaVu Sans Mono, Menlo, and Consolas-with-`size-adjust`. If
you change the fonts in `render.py` and the text starts clipping, this is the
number to change.

---

## What you build with

```yaml
stack:
  since_years: 1
  exclude_languages: [HTML, CSS, SCSS, "C#", TSQL]
  exclude_tech: []
  limit: 8
  sample_repos: 6
  timezone_offset: -5
```

Two separate problems, two separate mechanisms.

**GitHub's language stats measure bytes, and have no sense of time.** One large
legacy service outranks every current project indefinitely. On the account this
was built for, two C# repositories last touched in mid-2025 held 65 MB against
8 MB for everything else, so C# read as 66% of the profile, for someone who had
written nothing but TypeScript for two years. Setting `since_years: 1` flipped it
to TypeScript. Use `exclude_languages` for whatever still crowds in: markup
inflates badly against real code, and dead stacks are worth dropping outright.

Note that `#` starts a comment in YAML, so `"C#"` must be quoted.

**The languages API cannot see a framework, a cloud, or a database.** Next.js,
Vercel, Postgres and React all read as "TypeScript". So `{tech}` comes from
somewhere else: each recent repository's `package.json` and root file listing are
read and matched against a table of dependency and marker-file signatures in
`profilecard/techstack.py`, then ranked by **how many repositories use each
one**. Breadth is a better signal than byte volume, and one enormous repository
cannot distort it.

Add your own signatures by editing `DEPENDENCY_SIGNALS` and `FILE_SIGNALS` in
that module. A key ending in `/` matches a whole npm scope, so `@aws-sdk/` catches
every client package. Anything else is an exact match.

### Hours

`sample_repos` sets how many recently-pushed repositories to read commit
timestamps from, for `{busiest_hour}` and `{busiest_window}`. It is a sample,
not a census. A full history walk is the expensive thing this project avoids, and
and a few hundred recent commits is plenty to show when someone works. Set it to
`0` to skip the extra queries.

**`timezone_offset` is not optional if you display those.** GitHub returns commit
timestamps in UTC, so without it the hours are simply wrong. It is a fixed offset
rather than a named zone, so a daylight-saving change smears the histogram by an
hour. For a "when do you work" stat that is fine.

## Which repositories count

```yaml
github:
  affiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]
  star_affiliations: [OWNER]
  exclude_repos: []          # e.g. a vendored fork that would skew the numbers
  only_my_commits: true      # your commits, not everyone's
  count_lines: false         # see below
```

## Lines of code, and why it is off

Everything else on the card costs **four API calls and under ten seconds**. Line
counting is not like the rest: there is no aggregate endpoint for it, so it means
walking every commit of every repository, a hundred at a time.

On a small account that is fine. On a large one it is minutes and thousands of
API calls. During development, a walk of 31 repositories ran for over fifteen
minutes without finishing. So `count_lines` defaults to `false`.

The number is also weaker than it looks. It counts added minus deleted lines
across your commits, so one commit importing a vendored library, a lockfile, or a
generated client can add six figures and mean nothing.

If you want it anyway, set `count_lines: true` and add a `{loc}` field. The cost
is front-loaded: `cache/loc.json` keys each repository on its default branch head
SHA, so later runs only re-walk what actually moved. Delete that file to force a
full rebuild.
