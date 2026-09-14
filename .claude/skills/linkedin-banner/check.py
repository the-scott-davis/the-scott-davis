"""Pre-flight for a LinkedIn banner upload.

LinkedIn stores a *copy* of the image at upload time -- there is no API for a
member's cover photo and no hotlinking -- so the last step is always a human
dragging a file into a browser.  This does everything either side of that step:
proves the file is valid and current, says what it claims, and remembers what
was uploaded last time so the next run can say whether re-uploading is even
worth it.

    python3 .claude/skills/linkedin-banner/check.py            # report
    python3 .claude/skills/linkedin-banner/check.py --record   # mark uploaded

Exit codes: 0 ready, 1 stale (rebuild first), 2 invalid.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PNG = ROOT / "dist/linkedin_banner.png"
SVG = ROOT / "dist/linkedin_banner.svg"
CONFIG = ROOT / "config.yml"
STATE = Path(__file__).parent / "last-upload.json"

# LinkedIn's personal-profile cover photo.
WANT_SIZE = (1584, 396)
MAX_BYTES = 8 * 1024 * 1024

OK, BAD, WARN = "OK", "FAIL", "??"


def ago(ts: float) -> str:
    delta = dt.datetime.now() - dt.datetime.fromtimestamp(ts)
    mins = int(delta.total_seconds() // 60)
    if mins < 60:
        return f"{mins} min ago"
    if mins < 60 * 48:
        return f"{mins // 60} hours ago"
    return f"{mins // 1440} days ago"


def banner_text() -> list[str]:
    """What the banner currently says, in order, straight out of the SVG."""
    if not SVG.exists():
        return []
    raw = SVG.read_text(encoding="utf-8")
    lines = []
    for block in re.findall(r"<text[^>]*>(.*?)</text>", raw, re.S):
        text = re.sub(r"<[^>]+>", "", block).strip()
        if text:
            lines.append(text)
    return lines


def main() -> int:
    if "--record" in sys.argv:
        STATE.write_text(json.dumps({
            "uploaded_at": dt.datetime.now().isoformat(timespec="seconds"),
            "says": banner_text(),
        }, indent=2) + "\n")
        print(f"recorded: uploaded {dt.datetime.now():%Y-%m-%d %H:%M}")
        return 0

    problems, stale = [], []

    print(f"BANNER   {PNG.relative_to(ROOT)}")
    if not PNG.exists():
        print(f"  {BAD}  file does not exist -- run: make fetch")
        return 2

    from PIL import Image

    with Image.open(PNG) as im:
        size, mode = im.size, im.mode
    weight = PNG.stat().st_size

    flag = OK if size == WANT_SIZE else BAD
    print(f"  {flag}  {size[0]} x {size[1]} px" +
          ("" if flag == OK else f"  (LinkedIn wants {WANT_SIZE[0]} x {WANT_SIZE[1]})"))
    if flag == BAD:
        problems.append("wrong dimensions")

    flag = OK if PNG.suffix == ".png" and mode in ("RGB", "RGBA") else BAD
    print(f"  {flag}  PNG / {mode}")
    if flag == BAD:
        problems.append("not a usable PNG")

    flag = OK if weight <= MAX_BYTES else BAD
    print(f"  {flag}  {weight / 1024:.0f} KB  (limit {MAX_BYTES // 1024 // 1024} MB)")
    if flag == BAD:
        problems.append("over LinkedIn's size limit")

    print(f"  --  built {ago(PNG.stat().st_mtime)}")

    says = banner_text()
    if says:
        print("\nSAYS")
        for line in says:
            print(f"  {line}")

    print("\nFRESHNESS")
    if CONFIG.stat().st_mtime > PNG.stat().st_mtime:
        print(f"  {WARN}  config.yml changed after the last render")
        stale.append("config.yml is newer than the image")
    else:
        print(f"  {OK}  config.yml predates the render")

    # The numbers move every night, so an image built before the last rebuild
    # is showing figures the card has already moved past.
    try:
        head = subprocess.run(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%ct"],
            capture_output=True, text=True, check=True).stdout.strip()
        if head and int(head) > PNG.stat().st_mtime:
            print(f"  {WARN}  a commit landed after the last render")
            stale.append("the repo has moved since the image was built")
        else:
            print(f"  {OK}  newest commit predates the render")
    except (subprocess.CalledProcessError, ValueError):
        pass

    if STATE.exists():
        prev = json.loads(STATE.read_text())
        when = dt.datetime.fromisoformat(prev["uploaded_at"])
        days = (dt.datetime.now() - when).days
        print(f"  --  last uploaded {when:%Y-%m-%d} ({days} days ago)")
        changed = [(a, b) for a, b in zip(prev.get("says", []), says) if a != b]
        if not changed and len(prev.get("says", [])) == len(says):
            print(f"  {WARN}  nothing has changed since then -- no reason to re-upload")
        else:
            print("  --  changed since then:")
            for before, after in changed:
                print(f"        was  {before}")
                print(f"        now  {after}")
    else:
        print("  --  never uploaded from here")

    if problems:
        print(f"\nVERDICT  NOT VALID -- {'; '.join(problems)}")
        return 2
    if stale:
        print(f"\nVERDICT  STALE -- {'; '.join(stale)}.  Run `make fetch` first.")
        return 1
    print("\nVERDICT  ready to upload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
