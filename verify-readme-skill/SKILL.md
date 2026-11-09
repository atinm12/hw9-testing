---
name: verify-readme-skill
description: Reviews a project README against actual code implementation and reports missing or false claims. Use when checking README accuracy or verifying acceptance criteria, including when the docs may be out of date or out of sync with the code, or when setup or quickstart instructions reportedly don't work. Report-only; never edits files. Not for writing a new README or fixing grammar.
---

# Verify README claims

Check every claim a README makes about the project (files, functions, commands, features, acceptance criteria) against the actual code, and print a status report in the exact format below.

## Rules

- Do not fix or rewrite any files. Report missing or incorrect claims only.
- Cite evidence for every status: the README line, and the `file:line` in the code that proves or disproves the claim.
- Never mark a claim `[MET]` only because the file it mentions exists. Open the file and find the definition or behavior.

## Steps

1. **Pick the README.** Use the file the user named; otherwise `README.md` in the current working directory. If there is none, try `README.rst`, `readme.md`, then `docs/README.md`. If none exists, say so and stop.
2. **Run the checker tool if it is available.** Call `verify_readme_claims(project_path, readme_path)` with the absolute project root and the README path. In Claude Code it is `mcp__verify-readme-claims__verify_readme_claims`; if its schema isn't loaded yet, load it with ToolSearch first. Treat the output as leads, not a verdict:
   - It only checks file paths and names written as calls (`name()`). Names written without `()`, CLI flags, environment variables, counts and features described in prose are yours to check.
   - Its "not at the stated path, but found by name" notes are often false alarms for entries in an indented folder-tree diagram. Check the nesting before calling a path wrong.
   If the tool isn't available, do step 3 for every claim.
3. **Check each claim against the code** using [references/guidelines.md](references/guidelines.md). Read it before you start.
4. **Assign one status per claim:**
   - `[MET]`: the code does what the README says, where the README says it.
   - `[PARTIAL]`: it exists but differs: wrong location, call signature doesn't match, a number is off, or only part of a feature or acceptance criterion is implemented.
   - `[NOT MET]`: nothing in the code backs the claim.
   Claims that are external (a library, a URL), examples or placeholders, files the README says are generated or git-ignored, or things that can't be checked statically (play-feel, timing) get no status. List them under **Skipped** with the reason.
5. **Print the report** in the format below. Nothing before it and nothing after it.

## Output format

```text
## README check: <README path relative to project root>

**Result:** <N> claims checked · <a> MET · <b> PARTIAL · <c> NOT MET

[NOT MET] README l.<line> `<claim as written>` — <what the code actually has, with file:line, or "not defined anywhere"> — Fix: <exact correction>
[PARTIAL] README l.<line> `<claim>` — <what differs, with file:line> — Fix: <exact correction>
[MET] README l.<line> `<claim>` — <file:line>

**Skipped:** <claim (reason, l.<line>); claim (reason, l.<line>) — or "None">
```

Format rules:

- One line per claim. Order: all `[NOT MET]`, then `[PARTIAL]`, then `[MET]`; within each group, by README line number.
- `README l.<line>` is a single line number, never a range.
- Quote the claim exactly as the README writes it, in one pair of backticks.
- Every `[NOT MET]` and `[PARTIAL]` line ends with a concrete `Fix:` (the correct name, path, number or call). Don't hedge ("may have been renamed"): search the code, then state what you found.
- Write "not defined anywhere" only after searching the whole project.
- If the README has more than 40 checkable claims, list every `[NOT MET]` and `[PARTIAL]` line and the first 40 `[MET]` lines, then `[MET] … and <k> more`.
