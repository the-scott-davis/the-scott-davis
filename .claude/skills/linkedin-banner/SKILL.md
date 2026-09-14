---
name: linkedin-banner
description: Get the current LinkedIn banner ready to upload - validate it, show it, and hand over a clickable path. Use when asked to "update my LinkedIn banner", "upload the banner", "get me the banner", "is my banner current", or when invoked as /linkedin-banner. Rebuilds from fresh GitHub stats first if the image has gone stale.
---

# linkedin-banner

Hands over a validated, current `dist/linkedin_banner.png` and gets out of the
way. The upload itself stays manual, on purpose.

## Why this is not automated

There is no LinkedIn API for a member's cover photo. The member OAuth scopes
(`openid`, `profile`, `email`, `w_member_social`) are read-only for profile
fields; `w_member_social` publishes posts, it does not touch the profile. Only
Company **Pages** can have assets set programmatically, via the Marketing
Developer Platform.

That leaves driving the browser, which LinkedIn's User Agreement prohibits
(bots and automated access), and which would be selector-fragile against a UI
that is A/B tested constantly -- all to save a twenty-second drag-and-drop
roughly five times a year. **Do not offer to automate the upload.** If asked
directly, explain the above and let the user decide.

## The flow

1. **Check it.**

   ```bash
   python3 .claude/skills/linkedin-banner/check.py
   ```

   Exit codes: `0` ready, `1` stale, `2` invalid. The report covers dimensions,
   format, weight against LinkedIn's 8 MB limit, when it was built, what it
   currently says, and what has changed since the last upload.

2. **Act on the verdict.**

   | Exit | Meaning | Do this |
   |---|---|---|
   | `0` | Ready | Go to step 3 |
   | `1` | Stale -- config or repo moved since the render | `make fetch`, then re-check |
   | `2` | Invalid -- wrong size, bad format, too heavy | `make fetch`; if it still fails, the layout is broken, do not hand over a bad file |

   `make fetch` needs a token. This repo's own pattern:

   ```bash
   GITHUB_TOKEN="$(gh auth token)" .venv/bin/python -m profilecard
   ```

   Never hand over an image that failed validation. A wrong-sized banner is
   cropped by LinkedIn without warning, which is worse than no banner.

3. **Show it**, so the user sees what they are about to publish rather than
   taking the check's word for it. Send `dist/linkedin_banner.png` with
   SendUserFile.

4. **Hand over the path**, as a clickable markdown link:
   [dist/linkedin_banner.png](dist/linkedin_banner.png). To open Finder on it
   as well, load `mcp__ccd_host__reveal_path` via ToolSearch first.

5. **Give the four steps**, briefly -- profile → camera icon on the banner →
   Upload photo → pick the file → Apply.

6. **Offer to record it.** Once they confirm they have uploaded:

   ```bash
   python3 .claude/skills/linkedin-banner/check.py --record
   ```

   This is what makes the next run useful: it stores what the banner said, so
   next time the report can state plainly whether anything has changed and
   whether re-uploading is worth doing at all. Only record after the user says
   they actually uploaded -- recording early makes the next diff lie.

## What is worth re-uploading for

The numbers move nightly, but almost none of that movement is visible.
`17,845` becoming `17,849` is not a reason to touch anything. What is:

- a round number crossed (18,000 commits)
- `{github_years}` ticking over
- the calendar year rolling
- the stack line changing
- three months elapsed and none of the above

If the check reports nothing has changed since the last upload, **say so and
recommend skipping it.** The point of the skill is to make the upload easy, not
to manufacture reasons to do it.

## Files

| Path | What it is |
|---|---|
| `.claude/skills/linkedin-banner/check.py` | The pre-flight; also `--record` |
| `.claude/skills/linkedin-banner/last-upload.json` | Local state, gitignored |
| `dist/linkedin_banner.png` | The artifact, rebuilt by every `make fetch` |
| `config.yml` → `banner:` | Where the content and layout live |
