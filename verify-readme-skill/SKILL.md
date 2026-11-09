---
name: verify-readme-skill
description: Audits a project's README (or other docs) against the actual source code and reports claims that are false — files or directories that don't exist, functions or classes that aren't defined, imports that would fail, example calls whose arguments don't match the real signature. Use when the user asks whether a README or the docs are accurate, up to date, stale, out of sync, or match the code; asks to verify, audit, fact-check, validate or review a README; or before a release or PR that edits the README or renames code. Report-only — never edits files. Not for writing a new README, proofreading grammar or style, or reviewing code changes.
---

# Verify README claims

Find every claim in a README that the code does not back up, and report it in the fixed format below. This skill **reports only**: do not edit, create or delete any file, even to fix a problem you found, unless the user explicitly asks for edits after seeing the report.

## Steps

1. **Pick the README.** Use the file the user named. Otherwise use `README.md` in the current working directory; if it doesn't exist, try `README.rst`, `readme.md`, then `docs/README.md`. If none exists, tell the user and stop.
2. **Run the checker tool if it's available.** Call `verify_readme_claims(project_path, readme_path)` (in Claude Code: `mcp__verify-readme-claims__verify_readme_claims`) with the absolute project root and the README path. Treat its output as a list of leads, not a verdict:
   - Its "missing" items may be examples, external libraries or generated files.
   - Its "not at the stated path, but found by name" notes are often false alarms for entries in an indented folder-tree diagram. Check the tree's nesting before calling a path wrong.
   - It does not check imports, signatures, CLI flags or environment variables. You must.
   If the tool isn't available, skip this step and do step 3 for every claim.
3. **Check each claim against the code** using [references/guidelines.md](references/guidelines.md). Read that file before you start. Open the actual definition for every function, class, import and example call in the README. Never mark a claim valid only because the file it lives in exists.
4. **Classify every finding** with exactly one label from guidelines §9: `Missing`, `Wrong location`, `Signature mismatch`, `Unverifiable`, `Expected missing`, `External`, `Example / placeholder`.
5. **Write the report** in the format below. Nothing before it and nothing after it.

## Output format

Use this template exactly. Keep every heading, even when a section is empty.

```markdown
## README check: <README path relative to project root>

**Result:** <N> claims checked · <P> problems · <D> dismissed

### Problems

| # | Line | README says | Actual code | Label | Fix |
|---|------|-------------|-------------|-------|-----|
| 1 | 43 | `cache_player_logs()` in `data/cache.py` | Not defined anywhere; `data/cache.py` doesn't exist | Missing | Remove the sentence, or point to the real caching code |
| 2 | 118 | `get_vs_similar_teams("LeBron James")` | `get_vs_similar_teams(player_name, opponent_abbreviation, season="2024-25")` at `features/matchup_features.py:73` | Signature mismatch | `get_vs_similar_teams("LeBron James", "BOS")` |

### Dismissed

<one line: each dismissed claim, its label, and its line, e.g. "`.env` (Expected missing, l.48); `requests.get()` (External, l.27)" — or "None.">

### Not checked

<one line: claims you could not verify statically, with the reason — or "None.">
```

Rules:

- **One row per problem.** `Problems` holds only the labels `Missing`, `Wrong location`, `Signature mismatch` and `Unverifiable`. Order rows by README line number.
- **Line** is the README line number of the claim. Use a number, never a range like "7–8".
- **README says** quotes the claim exactly, in backticks.
- **Actual code** states what exists, with `file:line` whenever something was found. Write "Not defined anywhere" only after you have searched the whole project.
- **Fix** is a concrete replacement: the correct name, path or call. If you found no replacement, write "Remove, or add the missing code". Don't write hedges like "may have been renamed". Search first, then state what you found.
- **Don't list valid claims.** Count them in `Result` only.
- **Don't flag valid-but-unusual usage**, e.g. an example that passes a non-default argument value, as a problem.
- **If there are no problems**, put a single row reading `| – | – | No problems found | – | – | – |` in the table.
- Use no other headings, no preamble ("Here is the report"), and no closing summary.
