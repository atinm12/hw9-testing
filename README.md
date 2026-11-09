# 114HW8: Agent Toolkit (`verify_readme_claims`)

A lightweight agent toolkit built for CS 114 HW8. It combines a custom MCP server for code claim verification with a dedicated spec-checker skill to prevent hallucinated documentation during project handoffs.

## Motivation & Prompt Log Evidence

During HW7, I inherited another student's codebase and spent over an hour manually cross-referencing their README claims against their source files to see what actually worked. Later, when writing my own assignment submission, I had to double-check that every feature I claimed in my README was backed up by actual functions in code. 

My prompt log from HW7 ([`prompt_log.md`](https://github.com/atinm12/hw7-heist-phase2/blob/main/prompt_log.md) in my `hw7-heist-phase2` repo) highlighted this exact friction point. Answering "What cost me time?" for my handoff report, I wrote:

> *"What cost me time was definitely features that were described, but were different in the actual game. This cost me time because I was confused in what the README was talking about and directly referring to."*

This toolkit automates that sanity check so agents don't report non-existent features or quietly fix files while reviewing. The demonstration runs it on that same HW7 project's README.

---

## Toolkit Components

1. **`verify-readme-skill/`**: An inspection skill designed to audit project code against `README.md` claims. It strictly outputs a status report (`MET`, `PARTIAL`, `NOT MET`) with file and line citations without altering any files. `references/guidelines.md` holds the detailed rules for cross-referencing claims against code.
2. **`server.py` (MCP Server)**: A Python MCP server built with the MCP SDK's FastMCP API (called `MCPServer` in `mcp` 2.x), exposing the `verify_readme_claims` tool. It parses inline code, local links and code block references in the README, scanning Python source files (and JS/TS, Go, Rust, Java and similar) to verify that referenced files, directories, functions and modules exist. It returns a Markdown report of valid and missing claims. Bad input, such as a missing folder or README, returns an MCP error result instead of crashing, and all logging goes to stderr so the JSON-RPC stream on stdout stays clean.

---

## Setup & Installation

Requires Python 3.10 or newer.

### 1. Install

```bash
git clone https://github.com/atinm12/verify-readme-claims.git 114HW8
cd 114HW8
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python test_server.py            # should print "5/5 tests passed"
```

### 2. Register the MCP Server

Add the server to your client configuration file (`~/.codex/config.toml` or equivalent). Use absolute paths, and point `command` at the virtual environment's Python, since the system `python` doesn't have the `mcp` package:

```toml
[mcp_servers.verify_readme_claims]
command = "/path/to/114HW8/.venv/bin/python"
args = ["/path/to/114HW8/server.py"]
```

On Windows, use `command = "C:/path/to/114HW8/.venv/Scripts/python.exe"` and `args = ["C:/path/to/114HW8/server.py"]`.

For Claude Code, run this instead (it writes the same settings to `~/.claude.json`):

```bash
claude mcp add --scope user verify-readme-claims -- /path/to/114HW8/.venv/bin/python /path/to/114HW8/server.py
claude mcp list                  # should show: verify-readme-claims ... ✓ Connected
```

Restart the client after registering. In Codex, `/mcp` lists the server; in Claude Code the tool appears as `mcp__verify-readme-claims__verify_readme_claims`.

### 3. Install the Skill

Copy the skill folder into your agent's skills directory:

```bash
cp -R verify-readme-skill ~/.claude/skills/            # all projects
# or: cp -R verify-readme-skill <project>/.claude/skills/   # one project
```

Then ask something like *"Check if the README matches what the code actually does."* The agent loads the skill, calls `verify_readme_claims`, checks the rest by reading the code, and prints the status report.

---

## Usage

The tool takes two arguments:

```text
verify_readme_claims(project_path, readme_path)
```

`project_path` is the project's root directory; `readme_path` is absolute or relative to `project_path` (usually just `"README.md"`). For verbose server logs, set `LOG_LEVEL=DEBUG` in the server's environment.

---

## Demonstration, Iteration and Testing

- [`demonstration.md`](demonstration.md): the toolkit run on my HW7 project, with the MCP tool call and the checker in separate sessions, run more than once with fixes in between. Transcripts are in [`demo/hw7/`](demo/hw7/).
- [`iteration.md`](iteration.md): what failed, how I found it, what I changed, and the rerun results.
- [`demo/RESULTS.md`](demo/RESULTS.md): earlier testing on a copy of my `nba-predictor` project with deliberately planted README errors, plus a trigger test of the skill description with a decoy skill.
- `test_server.py` and `tests/`: automated tests for the server (direct calls, MCP calls, bad inputs, and a real stdio session).

## Repository Layout

```text
114HW8/
├── server.py                    # MCP server (verify_readme_claims tool)
├── requirements.txt
├── test_server.py               # server tests
├── tests/sample_project/        # small fixture project used by the tests
├── verify-readme-skill/
│   ├── SKILL.md                 # the checker skill
│   └── references/guidelines.md # cross-referencing rules
├── demonstration.md
├── iteration.md
└── demo/                        # transcripts, scripts and results of every run
```
