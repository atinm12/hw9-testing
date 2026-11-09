# Iteration and Failure Documentation

This documents two failures, both found by testing on real runs. Each has its own diagnosis, fix and rerun. Transcripts are linked inline; the demonstration runs are described in [`demonstration.md`](demonstration.md).

## Failure 1: A vague skill description

### What Went Wrong

When I first wrote my checker skill, I kept the description in the SKILL.md frontmatter very brief:

```yaml
name: verify-readme-skill
description: Checks things in the repo.
```

I wanted to see if the agent would pick it up when I asked for a project review. The body was just as vague: five steps such as "Open the file" and "Tell the user what is wrong", with no output format.

When I asked the agent to check if the README matched what the code actually did (Run 1 of the demonstration), it did load the skill, but the skill gave it nothing to follow. It ignored my MCP tool, read through the files with its standard file tools for 25 turns, gave a general free-form response, and didn't use any consistent output format. ([transcript](demo/hw7/run1/session2-checker.md))

To test discovery properly, I ran 9 prompts in fresh sessions with a decoy `readme-writer` skill installed next to mine: 5 that should trigger the checker and 4 that shouldn't. The vague skill **misfired on 2 of 9** ([results](demo/RESULTS.md#run-5-trigger-accuracy-with-a-decoy-skill-plus-full-execution)):
- For *"Someone filed an issue saying the quickstart instructions don't work"*, it never loaded the skill at all.
- For *"Is anything in the project documentation out of date…"*, the agent first tried to load a skill called `verify-readme-claims`, which doesn't exist (that's my MCP server's name).

### My Diagnosis

The agent only reads the name and description of a skill at startup to decide if it matches what you are trying to do. Because my description just said "Checks things in the repo," it was way too vague. The skill got picked up only when the prompt happened to share words with its *name* ("verify", "readme"). Prompts that described the problem without those words, like broken quickstart instructions, didn't match. And once loaded, the body had no output format and never mentioned the MCP tool, so the agent improvised both.

### What I Changed

I rewrote the description field in SKILL.md so it explicitly states what the skill does and when the agent should load it:

```yaml
name: verify-readme-skill
description: Reviews a project README against actual code implementation and reports missing or false claims. Use when checking README accuracy or verifying acceptance criteria.
```

Rerunning the 9-prompt test with this description fixed the wrong skill name, but it still missed the quickstart prompt: **1 of 9** ([results](demo/run6/grades.md)). So I kept that sentence and added the situations it was missing, plus what the skill is not for:

```yaml
description: Reviews a project README against actual code implementation and reports missing or false claims. Use when checking README accuracy or verifying acceptance criteria, including when the docs may be out of date or out of sync with the code, or when setup or quickstart instructions reportedly don't work. Report-only; never edits files. Not for writing a new README or fixing grammar.
```

I also added an explicit constraint under the rules section in the body of SKILL.md to prevent a common failure where agents try to fix issues while reviewing:

```text
Do not fix or rewrite any files. Report missing or incorrect claims only.
```

Finally, I gave the body concrete steps: which README to pick, when to call `verify_readme_claims` (and to load its schema first), what the tool can't check, and a defined output format, one `[MET]` / `[PARTIAL]` / `[NOT MET]` line per claim with the README line and a `file:line` citation.

### The Result

- **Discovery:** the final description triggered correctly on **9 of 9** prompts, including the quickstart one. It stayed out of the README-writing request (the decoy took it) and the grammar request ([results](demo/run7/grades.md)).
- **Execution:** I opened a fresh agent session and asked it to verify the project README against the code again (Run 2 of the demonstration). This time the agent loaded the full skill instructions immediately, called the MCP tool, checked 55 claims, and printed the results using the exact `[MET]` and `[NOT MET]` format with file and line citations. It ran the review without modifying any files: the project copy was byte-identical afterwards ([transcript](demo/hw7/run2/session2-checker.md)).

## Failure 2: A false "NOT MET" from counting text instead of code

### What Went Wrong

Run 2's report was well formatted, but its one finding was wrong:

```text
[NOT MET] README l.93 `There are 75 tests ...` — actual count: 8 + 17 + 14 + 15 + 4 + 1 = 59 — Fix: change "75 tests" to "59 tests"
```

The Run 1 checker had made the same claim. If I had trusted it, I would have "fixed" a correct README.

### My Diagnosis

I didn't take the report's word for it. I ran the HW7 test suite (`zsh test/run.sh`), which prints `RESULT 75 passed, 0 failed`. The agent had counted the 59 `T.add(` lines in the test files, but two of them sit inside `forEach` loops over the three levels: one registration in `playtest.test.js` becomes 3 tests, and 7 in `levels.test.js` become 21. My guidelines just said to "count or look up the actual value", which doesn't say *how* to count.

### What I Changed

I added a rule to `references/guidelines.md` (the skill's `SKILL.md` didn't change). I wrote it generically, with Python and JS examples that don't come from this project, so the rerun would test the rule rather than leak the answer:

> Count what the code produces **at runtime**, not how many times a pattern appears in the text. Registrations inside a loop multiply… If the project's test output reports a total, that total wins. If the count still can't be pinned down, list the claim under **Skipped** as unverifiable. Never report `[NOT MET]` based on a grep count alone.

### The Result

In a fresh session (Run 3), the agent found the loops itself and marked the claim correctly:

```text
[MET] README l.93 `There are 75 tests` — runtime count: core 8 + security 17 + vents 14 + levels 29 (8 fixed + 7×3 from `realLevels().forEach`) + powerups 4 + playtest 3 (1×`['l1','l2','l3'].forEach`) = 75
```

That gave 67 claims checked, 67 MET, no false findings and no files modified ([transcript](demo/hw7/run3/session2-checker.md)). Two minor format slips remain (blank lines between entries, and listing all `[MET]` lines after writing "… and 27 more"), which would be my next fix.

## Smaller problems found along the way

- **The demo setup checked the wrong README.** In Run 2, the MCP session's first attempt verified my HW8 README instead of the HW7 one, because the demo copies sat inside the `114HW8` git repo. I gave each copy its own git repo and reran ([failed attempt](demo/hw7/run2/session1-mcp-attempt1.md)).
- **The guidelines' code-parsing snippet was blocked.** It was a `python - <<'EOF'` heredoc, which common permission rules for `python3` don't allow. I rewrote it as a one-line `python3 -c` command.
- **The MCP tool alone over-reports wrong paths.** It flags bare file names in prose and folder-tree diagrams as "not at the stated path". The skill now tells the agent to treat those notes as leads and check the context.
