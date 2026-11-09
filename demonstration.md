# Demonstration of Toolkit

## Real Task Description
I tested the toolkit on my real repo from HW7: [`hw7-heist-phase2`](https://github.com/atinm12/hw7-heist-phase2), the browser stealth game I took over from a classmate and finished in Phase 2. My README for that project claims three levels, specific controls, powerups with exact timings (X-Ray 3 seconds with a 12 second cooldown, Stealth Mode 2.5 seconds with 2 uses), specific guard and camera tuning numbers, a code map naming about 20 functions such as `lineOfSight`, `computeRegions` and `drawStartScreen`, and "75 tests". These are exactly the kind of claims I had to check by hand in HW7. I wanted to see if my MCP server could find missing claims automatically, and then run my spec checker in a fresh session to audit the results without changing any code.

**Setup for every session:** a fresh copy of the HW7 project (`demo/hw7/hw7-heist/`, identical to my repo minus `.git`), Claude Code CLI 2.1.148 running headless (`claude -p`, default model `claude-sonnet-4-6`), the `verify-readme-claims` MCP server registered through [`demo/mcp-config.json`](demo/mcp-config.json), and project-only settings, so no other skills or servers from my machine were loaded. Each session is a separate `claude` process with no shared memory. The checker sessions were allowed to use Edit and Write, and the prompt didn't forbid changes, so "doesn't modify files" is tested rather than enforced. After each session, the copy was compared byte-for-byte with the original. Script: [`demo/hw7/run_session.sh`](demo/hw7/run_session.sh).

---

## Run 1

### Session 1: MCP Server Call
I asked the agent to run the `verify_readme_claims` tool on the test repository to compare `README.md` against the source files.

> Prompt: *"Run the verify_readme_claims tool on this project to compare README.md against the source files."*

The agent first loaded the tool's schema with `ToolSearch`, then called the tool with these arguments:

```json
{
  "name": "mcp__verify-readme-claims__verify_readme_claims",
  "input": {
    "project_path": "/Users/atinmathur/Downloads/114HW8/demo/hw7/run1/session1-mcp-target",
    "readme_path": "README.md"
  }
}
```

**Tool Output** (abridged; the full output is in the transcript):
```text
# README Claim Verification Report

- **Scanned:** 34 files, 212 distinct symbols
- **Claims checked:** 26  |  **Valid:** 26  |  **Missing:** 0
- **Accuracy:** 100%

## ✅ Valid claims (26)
### Files
- `index.html` (README line 14) → `index.html`
- `js/powerups.js` (README line 63) → `js/powerups.js`
- `vents.js` (README line 71) → `js/vents.js` _(not at the stated path, but found by name)_
- `js/utils.js` (README line 80) → `js/utils.js`
- ... 21 more files
### Directories
- `test` (README line 93) → `test`

## ❌ Missing claims (0)
```

The agent reported "All 26 claims in the README check out". It also called the 5 "found by name" notes "technically path inaccuracies", which they aren't: those are bare file names in prose (e.g. "`vents.js` and `player.js` already had their own jobs"). 3 turns, 13 s, $0.05.

**What this showed:** the tool only checks file paths and names written as calls (`name()`). My README writes function names without parentheses (`lineOfSight`, `computeRegions`), and it never names a test count or a timing as a path, so none of those were checked here. That is the checker skill's job.

Transcript: [`demo/hw7/run1/session1-mcp.md`](demo/hw7/run1/session1-mcp.md)

### Session 2: Spec Checker (separate session, original skill)
In a new session with the **original** skill installed ([`demo/hw7/skill-v1/`](demo/hw7/skill-v1/verify-readme-skill/SKILL.md), description *"Checks things in the repo."*), I asked:

> *"Check if the README matches what the code actually does."*

The agent loaded the skill, but the skill gave it nothing specific to follow. It never called the MCP tool, read the files with `grep` and `Read` for 25 turns, and wrote a free-form report: a table of functions marked "Valid", a list of files, and one discrepancy:

> **README line 93 — test count is wrong.** "There are 75 tests…" Actual count using `T.add` calls: 59. The README claims 75; the actual count is **59**.

**That finding is false.** I ran the HW7 test suite (`zsh test/run.sh`) and it prints `RESULT 75 passed, 0 failed`. Two of the `T.add` calls are inside `forEach` loops over the three levels, so 59 lines of source register 75 tests. No files were modified. 25 turns, 128 s, $0.31.

Transcript: [`demo/hw7/run1/session2-checker.md`](demo/hw7/run1/session2-checker.md) · Integrity: [`session2-checker.integrity.txt`](demo/hw7/run1/session2-checker.integrity.txt)

---

## Iteration between runs
The full write-up is in [`iteration.md`](iteration.md). In short:
- **Skill v2:** a precise description, the "Do not fix or rewrite any files" rule, the `[MET]` / `[PARTIAL]` / `[NOT MET]` output format with citations, and steps that say when to call the MCP tool.
- **Skill v3** (after Run 2): a guidelines rule to count tests and other repeated items the way the code produces them at runtime, never from a grep count.

---

## Run 2

### Session 1: MCP Server Call
Same prompt as Run 1. **The first attempt checked the wrong README.** It called the tool with `readme_path: "/Users/atinmathur/Downloads/114HW8/README.md"`, then on the whole `114HW8` folder, and reported on my HW8 README instead of the HW7 one. Cause: the demo copies sat inside my `114HW8` git repository, so the agent took that repo as "this project". I kept that transcript ([`session1-mcp-attempt1.md`](demo/hw7/run2/session1-mcp-attempt1.md)) and fixed the setup by giving each copy its own git repository, as the real HW7 project has.

On the rerun, the agent made the same call as in Run 1 (`project_path` = the HW7 copy, `readme_path` = `"README.md"`) and got the same result: 26 claims, 26 valid. The tool is deterministic. 3 turns, 11 s, $0.05.

Transcript: [`demo/hw7/run2/session1-mcp.md`](demo/hw7/run2/session1-mcp.md)

### Session 2: Spec Checker (separate session, skill v2)
Same prompt as Run 1, with [skill v2](demo/hw7/skill-v2/verify-readme-skill/SKILL.md). This time the agent loaded the skill, read the guidelines, **called `verify_readme_claims`**, then checked the claims the tool can't (controls, powerup timings, tuning numbers, function names, the test count) by reading the code. It printed the report in the defined format:

```text
## README check: README.md

**Result:** 55 claims checked · 54 MET · 0 PARTIAL · 1 NOT MET

[NOT MET] README l.93 `There are 75 tests in the core, security, vents, levels, powerups and playtest files` — actual count: 8 (core) + 17 (security) + 14 (vents) + 15 (levels) + 4 (powerups) + 1 (playtest) = 59 — Fix: change "75 tests" to "59 tests"

[MET] README l.27 `X: X-Ray, from level 2 on` — js/powerups.js:21; powerupsFor gives xray to level index ≥1 via js/game.js:14-15
[MET] README l.55 `12 second cooldown` — js/config.js:22 XRAY_COOLDOWN: 12
[MET] README l.82 `computeRegions` — js/level.js:86
...
**Skipped:** git clone URL (external, l.13); "takes about 40 seconds" (runtime, l.19); "99.7% of original lines" (git history required, l.61); ...
```

The format, citations and no-edit behavior all worked. No files were modified, and it checked twice as many claims as Run 1. **But it repeated the false "59 tests" finding** and even proposed a wrong fix. 41 turns, 381 s, $0.66.

Transcript: [`demo/hw7/run2/session2-checker.md`](demo/hw7/run2/session2-checker.md) · Integrity: [`session2-checker.integrity.txt`](demo/hw7/run2/session2-checker.integrity.txt)

---

## Run 3: Spec Checker after fixing the counting rule
Same prompt, a fresh session, with [skill v3](demo/hw7/skill-v3/verify-readme-skill/) (only `references/guidelines.md` changed; the new rule is written generically and doesn't mention this project). The agent called the MCP tool again, then counted the loops:

```text
**Result:** 67 claims checked · 67 MET · 0 PARTIAL · 0 NOT MET

[MET] README l.93 `There are 75 tests` — runtime count: core 8 + security 17 + vents 14 + levels 29 (8 fixed + 7×3 from `realLevels().forEach`) + powerups 4 + playtest 3 (1×`['l1','l2','l3'].forEach`) = 75
[MET] README l.89 `xrayOn` tells the renderer to skip fog — js/powerups.js:34; consumed at js/render.js:996
...
**Skipped:** git clone URL (external URL, l.13); "about 40 seconds" (runtime timing, l.19); bot alert scores 21/48/63 (requires running the bot, l.43); "99.7% of original lines" (requires git history, l.61); known-bugs descriptions (dynamic behavior, ll.98–105)
```

That matches the real test run (`RESULT 75 passed`), so the false finding is gone. No files were modified. Two small format slips remain: blank lines between entries, and after writing "… and 27 more" it listed them anyway. 36 turns, 467 s, $1.13.

Transcript: [`demo/hw7/run3/session2-checker.md`](demo/hw7/run3/session2-checker.md) · Integrity: [`session2-checker.integrity.txt`](demo/hw7/run3/session2-checker.integrity.txt)

---

## Summary

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| MCP tool session | 26/26 valid | 26/26 valid (after the wrong-README attempt) | – |
| Checker skill version | v1 (vague) | v2 (description, rule, format) | v3 (+ counting rule) |
| Checker called the MCP tool | no | yes | yes |
| Output format | free-form | `[MET]`/`[NOT MET]` report | `[MET]` report (minor slips) |
| Claims checked | not stated | 55 | 67 |
| False findings | 1 ("59 tests") | 1 ("59 tests") | 0 |
| Files modified | none | none | none |

My HW7 README turned out to be accurate. The value of the demonstration is that the toolkit confirmed that with citations for every claim, and that the iteration removed the one false accusation the earlier versions made.

**Reproduce:** from `demo/hw7/`, run `./run_session.sh <run-dir> <session-name> <none|skill-v1|skill-v2|skill-v3> <max-turns> "<prompt>"`.
