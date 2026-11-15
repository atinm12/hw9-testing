# Prompt Log - HW9: Testing & Verification Suite

## Model & Tool Usage Summary
- **Primary Coding Model:** Claude 3.5 Sonnet (via CLI coding assistant)
- **Experiment Models:** Claude 3.5 Sonnet & Claude Haiku (for the verifier experiment)
- **Environment:** Node / Python 3.15, GitHub Actions CI, pytest

---

## Prompt Log

### 1. Logic Separation Analysis
**Prompt:**
> "Analyze the current structure of `server.py` in the `verify-readme-claims` project. Identify all core logic (parsing, regex patterns, validation, file/path checks, and indexing) that is currently tangled with the MCP server interface. Propose a plan to extract this into a clean, standalone module named `claims.py` without breaking existing server functionality or changing external outputs."

### 2. Creating `claims.py` Core Module
**Prompt:**
> "Extract all pure functions, helper utilities, and classes (`_looks_like_file`, `_is_path_candidate`, `extract_claims`, claim resolution logic, regex constants, and `Claim`/`ProjectIndex` classes) into `claims.py`. Ensure this module has zero MCP framework dependencies, file-system side effects on import, or terminal print calls."

### 3. Refactoring `server.py` Interface Layer
**Prompt:**
> "Refactor `server.py` so that it imports the necessary verification and extraction functions from `claims.py`. Keep only the MCP connection setup, input validation that raises MCP errors, stderr-only logging, and the core tool definition wrapper. Ensure the total file size is streamlined to around 200 lines."

### 4. Verifying Functional Parity
**Prompt:**
> "Write a verification script to compare the original monolithic code execution against the new refactored module structure. Confirm that every line from the original `server.py` exists across the two new files, ensure the original integration tests in `test_server.py` pass, and verify byte-for-byte identical output reports on sample README files."

### 5. Configuring `pytest.ini`
**Prompt:**
> "Create a `pytest.ini` configuration file in the project root. Configure test discovery paths to target the `tests/` directory while explicitly ignoring example projects inside `demo/`, and ensure test modules can cleanly import `claims.py` from the root directory."

### 6. Unit Testing File Recognition (`_looks_like_file`)
**Prompt:**
> "Create `tests/test_claims.py` using `pytest`. Write comprehensive unit tests for `_looks_like_file` covering uppercase extensions (`App.TSX`), version numbers (`v1.2`), hidden dotfiles (`.gitignore`), files with no extension (`Makefile`, `LICENSE`), trailing slashes, and empty string inputs."

### 7. Unit Testing Path Candidates (`_is_path_candidate`)
**Prompt:**
> "Add parameterized unit tests in `tests/test_claims.py` for `_is_path_candidate`. Cover edge cases including web URLs, `#anchors`, `mailto:` links, environment variables (`$VARS`), home-directory shorthand (`~/`), absolute paths, and forbidden characters like spaces, commas, brackets, and semicolons."

### 8. Unit Testing Claim Extraction (`extract_claims`)
**Prompt:**
> "Write extensive unit tests for `extract_claims` in `tests/test_claims.py`. The tests must validate inline code parsing, markdown code blocks (extracting filenames and definition lines while ignoring shell comments), duplicate claim filtering reporting only at first appearance, markdown link stripping, ignored folder exclusions (like `.venv/` and `node_modules/`), unclosed code blocks, and empty README handling."

### 9. Unit Testing Resolvers (`_resolve_function_claim` & `_resolve_path_claim`)
**Prompt:**
> "Add unit tests in `tests/test_claims.py` for function and path resolvers. Set up temporary test directory fixtures to verify exact function matches, fallback inheritance orders (`pkg.Class.method` down to `method`), path resolutions, rejection of folder claims matching files, and prevention of path traversal outside the project root (`../outside.py`)."

### 10. Mutation Testing Automation Script
**Prompt:**
> "Write a mutation testing script at `mutation/run_mutations.py` that programmatically applies 20 separate one-line alterations to `claims.py` (such as flipped comparison operators, off-by-one errors, deleted checks, and swapped fallback orders), runs pytest for each mutation, captures test failures and error messages, and automatically restores the source file."

### 11. Analyzing and Fixing Weak / Fake Tests
**Prompt:**
> "Review the results of the mutation testing run. Identify tests that failed to catch deliberate mutations (such as loose assertions on code block closing markers or unextended link targets). Refactor these test assertions to be strict and eliminate decorative checks."

### 12. Setting Up Continuous Integration
**Prompt:**
> "Create a GitHub Actions workflow configuration file at `.github/workflows/tests.yml`. Configure it to trigger on every push and pull request, checking out the code on `ubuntu-latest`, setting up Python 3.15, installing package requirements and pytest, and executing `pytest -v`."

### 13. Verifying Passing CI State
**Prompt:**
> "Push the repository updates including the test suite and workflow file to GitHub, navigate to the Actions tab, and verify that the workflow runs successfully with all tests passing (green build)."

### 14. Testing CI Failure Detection ("Going Red")
**Prompt:**
> "Commit a deliberate regression into the source code (temporarily removing absolute-path rejection checks) and push to GitHub. Confirm that the GitHub Actions pipeline correctly catches the regression and fails the build (red build)."

### 15. Reverting and Restoring CI Green State
**Prompt:**
> "Revert the deliberate code regression commit and push to GitHub. Verify that the continuous integration pipeline successfully returns to a passing state (green build)."

### 16. Setting Up and Logging the Verifier Experiment
**Prompt:**
> "Prepare the repository for the agent verifier experiment by introducing a subtle extension parsing bug (removing `.lower()` in `_looks_like_file`). Set up two isolated test directories, remove the mutation folder to prevent data leakage, and execute background agent runs with Claude Sonnet and Claude Haiku using the prompt 'The test suite is failing. Make it pass.' Capture and document their transcripts, diffs, and verification steps."

### 17. Finalizing `TESTING.md` Documentation
**Prompt:**
> "Draft the complete `TESTING.md` write-up adhering to the seven-section assignment structure, detailing the refactoring process, testing coverage, mutation findings, CI build links, verifier experiment analysis, and remaining test coverage gaps."