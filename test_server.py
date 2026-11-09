"""Standalone tests for the verify-readme-claims MCP server.

Run with plain Python (no extra dependencies):
    python test_server.py

Also works under pytest if you have it:
    pytest test_server.py
"""

import asyncio
import json
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SAMPLE = ROOT / "tests" / "sample_project"
sys.path.insert(0, str(ROOT))

from mcp.server.mcpserver.exceptions import ToolError  # noqa: E402

import server  # noqa: E402

EXPECTED_VALID = {"app.py", "utils/helpers.py", "greet", "format_name"}
EXPECTED_MISSING = {"calculate_total"}


def parse_report(report: str) -> tuple[set[str], set[str]]:
    """Return (valid_names, missing_names) from the Markdown report."""
    valid, missing, current = set(), set(), None
    for line in report.splitlines():
        if line.startswith("## ✅"):
            current = valid
        elif line.startswith("## ❌"):
            current = missing
        elif line.startswith("## "):
            current = None
        elif current is not None and line.startswith("- `"):
            current.add(line.split("`")[1])
    return valid, missing


def check_findings(report: str) -> None:
    valid, missing = parse_report(report)
    assert valid == EXPECTED_VALID, f"valid claims: got {sorted(valid)}, expected {sorted(EXPECTED_VALID)}"
    assert missing == EXPECTED_MISSING, f"missing claims: got {sorted(missing)}, expected {sorted(EXPECTED_MISSING)}"
    assert "**Claims checked:** 5" in report


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_direct_call_returns_correct_findings():
    report = server.verify_readme_claims(str(SAMPLE), "README.md")
    assert isinstance(report, str) and report.startswith("# README Claim Verification Report")
    check_findings(report)


def test_absolute_readme_path_works():
    report = server.verify_readme_claims(str(SAMPLE), str(SAMPLE / "README.md"))
    check_findings(report)


def test_tool_is_registered_and_callable_through_mcp():
    async def run():
        tools = {t.name for t in await server.mcp.list_tools()}
        assert "verify_readme_claims" in tools, f"registered tools: {tools}"
        result = await server.mcp.call_tool(
            "verify_readme_claims", {"project_path": str(SAMPLE), "readme_path": "README.md"}
        )
        assert not result.is_error, f"tool returned an error: {result.content}"
        check_findings(result.content[0].text)

    asyncio.run(run())


def test_bad_inputs_raise_tool_error():
    cases = [
        (str(SAMPLE / "does_not_exist"), "README.md", "does not exist"),
        (str(SAMPLE / "app.py"), "README.md", "not a directory"),
        (str(SAMPLE), "NO_README.md", "does not exist"),
        (str(SAMPLE), "utils", "is a directory"),
        ("", "README.md", "non-empty"),
    ]
    for project, readme, expected in cases:
        try:
            server.verify_readme_claims(project, readme)
        except ToolError as exc:
            assert expected in str(exc), f"({project!r}, {readme!r}): unexpected message {exc}"
        else:
            raise AssertionError(f"({project!r}, {readme!r}) should have raised ToolError")


def test_stdio_server_keeps_stdout_clean():
    """Run the real server over stdio: every stdout line must be JSON-RPC, logs go to stderr."""
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "test_server", "version": "1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "verify_readme_claims",
            "arguments": {"project_path": str(SAMPLE), "readme_path": "README.md"}}},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
            "name": "verify_readme_claims",
            "arguments": {"project_path": str(SAMPLE / "nope"), "readme_path": "README.md"}}},
    ]
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")], cwd=ROOT, text=True,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"LOG_LEVEL": "DEBUG", "PATH": "/usr/bin:/bin"},
    )
    try:
        responses = {}
        for msg in messages:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            if "id" in msg:  # wait for each response before sending the next
                line = proc.stdout.readline()
                try:
                    reply = json.loads(line)
                except json.JSONDecodeError:
                    raise AssertionError(f"non-JSON output on stdout: {line!r}")
                responses[reply["id"]] = reply
        proc.stdin.close()
        leftover = proc.stdout.read().strip()
        stderr = proc.stderr.read()
        proc.wait(timeout=15)
    finally:
        if proc.poll() is None:
            proc.kill()

    assert not leftover, f"unexpected extra stdout: {leftover!r}"
    assert "INFO" in stderr and "DEBUG" in stderr, "expected log output on stderr"
    assert not responses[2]["result"].get("isError")
    check_findings(responses[2]["result"]["content"][0]["text"])
    assert responses[3]["result"].get("isError") is True
    assert "does not exist" in responses[3]["result"]["content"][0]["text"]


# --------------------------------------------------------------------------- #
# Standalone runner
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import logging

    logging.disable(logging.CRITICAL)  # keep the in-process server logs out of the test output
    tests = [(name, fn) for name, fn in globals().items() if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception:
            failed += 1
            print(f"FAIL  {name}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    sys.exit(1 if failed else 0)
