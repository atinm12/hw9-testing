"""Render a `claude -p --output-format stream-json` transcript as readable Markdown.

Usage:
    python demo/render_transcript.py demo/run1/transcript.jsonl > demo/run1/transcript.md
"""

import json
import sys
from pathlib import Path


def text_of(content) -> str:
    if not isinstance(content, str):
        content = "\n".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    # MCP tools with structured output arrive as {"result": "..."}; unwrap for readability.
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and set(parsed) == {"result"} and isinstance(parsed["result"], str):
            return parsed["result"]
    except (json.JSONDecodeError, TypeError):
        pass
    return content


def main(path: str) -> None:
    out = []
    step = 0
    # stream-json doesn't echo the prompt, so read it from prompt.txt next to the transcript.
    prompt_file = Path(path).with_name("prompt.txt")
    prompt = prompt_file.read_text(encoding="utf-8").strip() if prompt_file.exists() else None
    for line in open(path, encoding="utf-8"):
        event = json.loads(line)
        kind = event.get("type")

        if kind == "system" and event.get("subtype") == "init":
            mcp = ", ".join(f"{s['name']} ({s['status']})" for s in event.get("mcp_servers", []))
            tools = [t for t in event.get("tools", []) if t.startswith("mcp__")]
            out += [
                "# Session transcript", "",
                f"- **Model:** `{event.get('model')}`",
                f"- **Working directory:** `{event.get('cwd')}`",
                f"- **MCP servers:** {mcp or 'none'}",
                f"- **MCP tools available:** {', '.join(f'`{t}`' for t in tools) or 'none'}",
                f"- **Permission mode:** `{event.get('permissionMode')}`", "",
            ]
            if prompt:
                out += ["## User prompt", "", "> " + prompt.replace("\n", "\n> "), ""]

        elif kind == "user" and not out[-1:] == ["## User prompt"]:
            msg = event["message"]
            if isinstance(msg.get("content"), str):
                out += ["## User prompt", "", "> " + msg["content"].replace("\n", "\n> "), ""]
                continue
            for c in msg.get("content", []):
                if c.get("type") == "tool_result":
                    status = "ERROR" if c.get("is_error") else "ok"
                    out += [f"#### Tool result ({status})", "", "````text", text_of(c.get("content", "")).rstrip(), "````", ""]
                elif c.get("type") == "text":
                    out += ["## User prompt", "", "> " + c["text"].replace("\n", "\n> "), ""]

        elif kind == "assistant":
            for c in event["message"]["content"]:
                if c["type"] == "text" and c["text"].strip():
                    out += ["### Assistant", "", c["text"].strip(), ""]
                elif c["type"] == "tool_use":
                    step += 1
                    out += [
                        f"### Tool call {step}: `{c['name']}`", "",
                        "```json", json.dumps({"name": c["name"], "input": c["input"]}, indent=2), "```", "",
                    ]

        elif kind == "result":
            out += [
                "---", "",
                "## Run summary", "",
                f"- **Outcome:** `{event.get('subtype')}`{' (error)' if event.get('is_error') else ''}",
                f"- **Turns:** {event.get('num_turns')}",
                f"- **Duration:** {event.get('duration_ms', 0) / 1000:.1f}s",
                f"- **Cost:** ${event.get('total_cost_usd', 0):.4f}",
                f"- **Permission denials:** {len(event.get('permission_denials') or [])}",
            ]
            for d in event.get("permission_denials") or []:
                out.append(f"  - `{d.get('tool_name')}` {json.dumps(d.get('tool_input'))[:200]}")
            out.append("")

    print("\n".join(out))


if __name__ == "__main__":
    main(sys.argv[1])
