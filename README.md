# verify-readme-claims MCP Server

An MCP server that checks whether the files, directories and functions a README mentions actually exist in a project. Built with the MCP Python SDK 2.x (`MCPServer`, formerly FastMCP).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

```bash
python server.py        # stdio transport, as MCP clients launch it
mcp dev server.py       # MCP Inspector for interactive testing (requires Node.js)
LOG_LEVEL=DEBUG python server.py   # verbose logs
```

All logs go to **stderr**, because stdout carries the MCP JSON-RPC stream. Bad input (a missing directory, a missing, empty or binary README, unreadable paths) returns an MCP error result (`isError: true`) with a readable message. It does not crash the server.

Connect it to Claude Code:

```bash
claude mcp add verify-readme-claims -- /absolute/path/to/114HW8/.venv/bin/python /absolute/path/to/114HW8/server.py
```

## Claude Code skill

`verify-readme-skill/SKILL.md` tells Claude when to run this tool and how to sort its findings into real problems, examples and external references. To install it, copy the folder into `~/.claude/skills/` (all projects) or `<project>/.claude/skills/` (one project).

## Testing

```bash
python tests/run_sample.py
```

This runs the tool against `tests/sample_project/`. That project's README mentions an existing file and functions plus one function that doesn't exist, and the script checks that each is classified correctly.

## Demo

[demo/RESULTS.md](demo/RESULTS.md) records four headless Claude Code runs against a copy of a real project whose README has deliberately planted errors. It compares the tool alone, the simple skill, and the revised skill, with full transcripts and a `command.sh` to rerun each.

## Tool: `verify_readme_claims(project_path, readme_path)`

`readme_path` can be absolute or relative to `project_path`. The tool returns a Markdown report of valid and missing claims.

**What counts as a claim**

| README content | Claim type |
|---|---|
| Local Markdown links, e.g. `[guide](docs/guide.md)` | file or directory |
| Inline code that looks like a path: `src/app.py`, `.env.example`, `docs/` | file or directory |
| File names in fenced code blocks, e.g. `python server.py` | file |
| Inline code calls: `load_config()`, `Parser.parse()` | function |
| `def name` / `function name` in inline code or code blocks | function |

**How claims are checked**

- Paths are resolved against the project root, then against the README's folder. If a file isn't at the stated path but a file with the same name exists elsewhere, the claim is marked valid with a note.
- Functions are found by parsing Python files with `ast` (functions, classes, methods) and by regex for JS/TS, Go, Rust, Ruby, Java, C-family and similar languages.
- `.git`, `.venv`, `node_modules`, `__pycache__`, `build`, `dist` and similar folders are skipped.
- Python built-ins (e.g. `print()`), decorators (`@mcp.tool()`), URLs and absolute paths are ignored.
