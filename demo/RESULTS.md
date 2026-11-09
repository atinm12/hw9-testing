# Demonstration results

Target: a copy of the `nba-predictor` project with errors planted in its README. Agent: Claude Code CLI 2.1.148 running headless (`claude -p`), with the `verify-readme-claims` MCP server, no skill installed. Model: `claude-sonnet-4-6` (the CLI default). Each run's `command.sh` reproduces it.

Prompt for both runs:

> Use the verify_readme_claims tool to check whether the README in this project is accurate, and report what it finds.

## Planted errors

| # | Error | Tool can detect? | Run 1 README | Run 2 README |
|---|---|---|---|---|
| 1 | `injury_features.py` in the folder tree (doesn't exist) | Yes | present | **fixed** |
| 2 | `compare_to_vegas()` in `models/predict.py` (really `compare_vs_vegas()` in `evaluate.py`) | Yes | present | **fixed** |
| 8 | `cache_player_logs()` in `data/cache.py` (neither exists) | Yes | absent | **added** |
| 3 | `--quick` flag renamed to `--fast` | No | present | present |
| 4 | `WEATHER_API_KEY` (never read by the code) | No | present | present |
| 5 | `get_streak_stats` import (doesn't exist) | No | present | present |
| 6 | `get_vs_similar_teams("LeBron James")` leaves out a required argument | No | present | present |
| 7 | "XGBoost + LightGBM ensemble" (LightGBM not used) | No | present | present |

Run 2's README changes are in [run2/readme.diff](run2/readme.diff).

## Results

| | Run 1 | Run 2 |
|---|---|---|
| Tool calls | `ToolSearch` → `verify_readme_claims` | `ToolSearch` → `Bash find README*` → `verify_readme_claims` |
| `verify_readme_claims` arguments | `project_path` = target (absolute), `readme_path` = `"README.md"` | same |
| Tool output | 24 claims, 21 valid, 3 missing | 24 claims, 21 valid, 3 missing |
| Missing claims reported | `.env`, `injury_features.py`, `compare_to_vegas` | `.env`, `data/cache.py`, `cache_player_logs` |
| `.env` | dismissed as gitignored ✅ | dismissed as gitignored ✅ |
| Folder-tree "found by name" notes | wrongly read as unclear paths ❌ | wrongly read as incorrect paths ❌ |
| Planted errors found | **2 / 7** (#1, #2) | **1 / 6** (#8) |
| Tool-invisible errors found | 0 / 5 | 0 / 5 |
| Turns / time / cost | 3 / 18.4s / $0.058 | 4 / 21.7s / $0.066 |

## Consistency findings

- **The tool is deterministic and tracks the README exactly.** The two fixed errors disappeared from the missing list, `compare_vs_vegas` moved to valid with its real location (`models/evaluate.py:79`), and the new `data/cache.py` / `cache_player_logs` claim appeared. Line numbers shifted by +2 to match the inserted lines. Everything else was identical.
- **The agent's pattern was consistent.** Both runs made one call with the same argument shape, accepted the tool's report as complete, never read source code, and dismissed `.env` correctly.
- **It repeated the same mistake both times.** Both runs read the tool's "not at the stated path" notes for folder-tree entries as README errors, and Run 2 stated it more strongly ("incorrect paths ... could confuse readers"). The paths in the tree are correct.
- **Minor variation:** Run 2 added a `find README*` step before calling the tool. Run 2 also said `cache_player_logs` "can't be verified" because its file is missing, which isn't accurate: the tool searches the whole project for functions, not just that file.
- **Conclusion:** with the tool alone, the agent reliably reports exactly what the tool can detect and nothing more. The 5 errors the tool can't detect were missed in both runs, and the false "wrong path" advice appeared in both. Those are the gaps the skill and its guidelines are meant to close.

## Run 3: checker skill, write access allowed

Same target as Run 2, copied to `nba-predictor-run3/` with the skill installed in `.claude/skills/verify-readme-skill/` (the simple `SKILL.md` plus `references/guidelines.md`). The MCP server was connected. **Edit and Write were allowed** and the prompt didn't forbid changes, so "no modifications" is tested, not enforced.

> Use the verify-readme-skill skill to review README.md in this project.

### File integrity

Every file in the workspace (107 files, excluding `.venv` and `demo/run3/`) was fingerprinted with SHA-256 before and after the session ([run3/file-integrity.txt](run3/file-integrity.txt)):

```
compared 107 -> 107 files
  no differences: every file is byte-identical
```

The transcript has **no Edit, Write or file-changing shell calls**. One read-only call was blocked: the guidelines' AST snippet, run as a `python3` heredoc, didn't match the `Bash(python3:*)` permission rule. The agent fell back to reading the files directly.

### Tool calls

`Skill(verify-readme-skill)` → `Read README.md` → `Read references/guidelines.md` → `find` (list files) → `python3` AST snippet (**denied**) → `Read player_features.py`, `matchup_features.py`, `evaluate.py`. It **never called the `verify_readme_claims` MCP tool**, because the simple `SKILL.md` doesn't mention it. 10 turns, 90.8s, $0.181.

### Findings vs answer key (Run 2 README, 6 planted errors)

| # | Planted error | Run 2 (tool only) | Run 3 (skill) |
|---|---|---|---|
| 8 | `cache_player_logs()` / `data/cache.py` missing | ✅ | ✅ |
| 5 | `get_streak_stats` import doesn't exist | ❌ | ✅ "would raise ImportError" |
| 6 | `get_vs_similar_teams("LeBron James")` leaves out a required argument | ❌ | ✅ signature mismatch, with the real signature |
| 3 | `--quick` renamed to `--fast` | ❌ | ❌ **wrongly listed as valid** ("pipeline.py present"); it never opened `pipeline.py` |
| 4 | `WEATHER_API_KEY` not used | ❌ | ❌ not mentioned |
| 7 | LightGBM not used | ❌ | ❌ not mentioned |
| | **Total** | **1 / 6** | **3 / 6** |

Other differences from Run 2:
- ✅ **No false path advice.** It correctly confirmed the folder-tree entries are at their stated paths.
- ⚠️ One weak extra finding: it flagged `compute_rolling_averages(df, windows=[3, 7])` as "misleading" because the default is `[5, 10, 20]`. Passing a custom argument is valid, so this isn't a real error.
- ⚠️ `.env` wasn't mentioned at all (Run 2 correctly dismissed it).

### Conclusions

- **The skill reports and doesn't modify anything.** That held even with write tools available and no instruction against editing. The simple `SKILL.md` says only "Tell the user what is wrong", which the agent read as report-only. Nothing in the skill *guarantees* this, though: adding "Don't edit the README unless the user asks" would make it explicit.
- **The guidelines are what made the difference.** Following `guidelines.md`, the agent read the source code and caught the import and signature errors the tool misses (1 of 6 → 3 of 6).
- **Remaining gaps:** CLI flags, environment variables and dependencies in prose were still missed, and the `--fast` flag was falsely marked valid. Those claim types aren't in the guidelines (only `pyproject.toml` entry points are). The skill also doesn't use the MCP tool, and the heredoc form of the guidelines' AST snippet is blocked by common permission settings.

## Run 4: precise description + output format (vagueness fix)

`SKILL.md` rewritten: a 643-character description saying what it checks, when to use it, that it's report-only and what it's not for; concrete steps (which README, call the MCP tool, read definitions, never mark a claim valid just because its file exists); a fixed report template with column rules. Same target as Run 3 (`nba-predictor-run4/`), Edit/Write allowed. Transcripts are in [run4/](run4/).

### Triggering

| Prompt | Old skill ("Checks things in the repo.") | New skill |
|---|---|---|
| "Are the docs in this project still in sync with the code?" | ✅ triggered (first tried a nonexistent skill `verify-readme-claims`) | ✅ triggered |
| "I'm about to tag v1.0. Is there anything in the project documentation that no longer matches the implementation?" | ✅ triggered (same wrong name first) | ✅ triggered |
| "Someone filed an issue saying the quickstart instructions don't work…" | ✅ triggered | ✅ triggered |
| "What does pipeline.py do? Answer in two sentences." (should not trigger) | not run | ✅ not triggered |

These tests **don't show a triggering difference**: the old skill triggered as well. Its name contains "verify" and "readme", and with few skills installed the model picks it for any doc-related prompt. The only difference is that the old skill twice tried a nonexistent skill name before finding the right one; the new one never did. A real difference would need a crowded skill list (e.g. a competing docs-writing skill) to show up.

### Output and accuracy (prompt 1, full run)

| | Old skill | New skill |
|---|---|---|
| Format | Free-form headings, valid claims listed | Template followed: one table, `Dismissed` and `Not checked` lines, valid claims counted only |
| Planted errors found (of 6) | 3 | **4**: adds `--fast` → `--quick` (`pipeline.py:90`), because of the "never mark valid just because the file exists" rule |
| Concrete fixes | None | Every row (e.g. `python pipeline.py --quick`, `get_vs_similar_teams("LeBron James", "BOS")`) |
| False findings | None | None (the `windows=[3, 7]` false finding from Run 3 is gone) |
| Files modified | none | none: 142 files byte-identical before/after ([run4/file-integrity.txt](run4/file-integrity.txt)) |
| Turns / time / cost | 15 / 52s / $0.142 | 16 / 115s / $0.243 |

Remaining issues with the new skill:
- It **never called the MCP tool**, despite step 2. The tool is deferred in Claude Code and needs a `ToolSearch` call first; the agent said "running the checker tool" and then didn't.
- One preamble line ("I now have all the information…") before the report, against the "nothing before it" rule. It also double-wrapped backticks in the *README says* column.
- Still missed `WEATHER_API_KEY` and LightGBM, and wrote "Not checked: None" anyway. Env vars and dependencies aren't in the guidelines yet.
- The guidelines' heredoc AST snippet was blocked again by the `Bash(python3:*)` rule.
