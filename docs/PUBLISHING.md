# Publishing and scheduling

The card is rebuilt **on the owner's machine**, not by GitHub Actions, and then
pushed like any other commit.

That is a deliberate security choice rather than a convenience one. Building in
CI would mean creating a personal access token with `repo` scope — read and
write access to every repository you own — and handing a copy to GitHub to store
as a secret. It would sit there indefinitely, and rotating it would mean
remembering it exists.

Building locally needs none of that. The `gh` CLI you are already signed in to
holds a token in the macOS keyring, and `scripts/nightly.sh` reads it at the
moment of use:

```bash
GITHUB_TOKEN="$(gh auth token)" "$PYTHON" -m profilecard
```

It exists in one process's environment for a few seconds. Nothing is written to
disk, committed, or stored by GitHub. Rotating it is `gh auth refresh` — there
is no second credential to remember.

The consequence of this choice is that **no workflow in this repository handles a
secret**, and none can be triggered by anyone without write access. The only
workflow left runs the tests.

## One-time setup

```bash
make venv                       # virtualenv for the scheduled job
./scripts/nightly.sh            # prove it works before scheduling it
```

`make venv` builds from `python3.11` rather than whatever `python3` points at.
Pyenv-managed interpreters are frequently linked against an OpenSSL that is no
longer installed, which breaks HTTPS entirely — the failure looks like a network
problem and is not one. The `venv` target checks for this and refuses to produce
a broken environment.

## Scheduling it

The script is a self-contained one-shot: it takes no arguments, resolves its own
location, exits non-zero on failure, and is safe to run at any time. Point
whatever scheduler you already use at it.

```
/ABSOLUTE/PATH/TO/REPO/scripts/nightly.sh
```

Run `pwd` in the repository to get that path. Use an absolute one — schedulers
generally do not expand `~`, and rarely inherit your interactive shell's `PATH`.

Any of cron, launchd, pm2, systemd timers, or a scheduler you already run will
do. Two things are worth checking whichever you pick:

- **Sleep behaviour.** A plain cron schedule only fires while the machine is
  awake, so a desktop that sleeps at midnight simply skips that night. On macOS,
  launchd runs a missed job on wake, which is the better fit for anything that
  sleeps.
- **`PATH`.** The script needs `git` and `gh` on it. If your scheduler starts
  with a minimal environment, set `PATH` explicitly in the job definition.

Missing a night is harmless. The card on GitHub simply stays as it was until the
next successful run.

## What the script does

1. Refuses to run if the working tree has uncommitted changes outside `dist/`,
   so a scheduled job can never bury work in progress.
2. Fast-forwards from `origin/main`.
3. Reads the token from the keyring, fetches stats, renders both SVGs.
4. Commits and pushes **only if the card actually changed**.

Any failure leaves the committed card untouched. A stale card is a much better
outcome than a wrong one, so nothing is published unless the whole run succeeded.

## If it stops working

```bash
./scripts/nightly.sh            # run it by hand; the error will say what broke
```

| Symptom | Cause |
|---|---|
| `gh is not signed in` | `gh auth login` |
| `no virtualenv` | `make venv` |
| Card shows 2 commits instead of thousands | The `gh` token lost `repo` scope. `gh auth refresh -s repo` |
| `working tree has uncommitted changes` | Commit or stash them; the guard is doing its job |
