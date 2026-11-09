#!/bin/zsh
# Run one demo session on a fresh copy of the HW7 project.
# Usage: run_session.sh <run-dir> <session-name> <skill-version: none|skill-v1|skill-v2|skill-v3> <max-turns> <prompt>
set -e  # stop if any setup step fails, so a session never runs half-configured
H=${0:A:h}; RUN=$H/$1; NAME=$2; SKILL=$3; MT=$4; PROMPT=$5
T=$RUN/$NAME-target
mkdir -p "$RUN"; rm -rf "$T"; cp -R "$H/hw7-heist" "$T"
# Give the copy its own git repo, like the real HW7 project. Without this, the agent
# sees the enclosing 114HW8 repo as the project root and may check the wrong README.
git -C "$T" init -q
TOOLS="mcp__verify-readme-claims__verify_readme_claims Read Grep Glob"
if [[ $SKILL != none ]]; then
  [[ -f "$H/$SKILL/verify-readme-skill/SKILL.md" ]] || { echo "missing skill $SKILL" >&2; exit 1; }
  mkdir -p "$T/.claude/skills"; cp -R "$H/$SKILL/verify-readme-skill" "$T/.claude/skills/"
  TOOLS="Skill $TOOLS Edit Write Bash(python3:*) Bash(ls:*) Bash(find:*) Bash(grep:*) Bash(wc:*) Bash(cat:*)"
fi
print -r -- "$PROMPT" > "$RUN/$NAME.prompt.txt"
cd "$T" && ~/.local/bin/claude -p "$PROMPT" \
  --output-format stream-json --verbose --setting-sources project \
  --strict-mcp-config --mcp-config "$H/../mcp-config.json" --permission-mode dontAsk \
  --allowedTools "$TOOLS" --max-turns $MT < /dev/null > "$RUN/$NAME.jsonl"
cp "$RUN/$NAME.prompt.txt" "$RUN/prompt.txt"
python3 "$H/../render_transcript.py" "$RUN/$NAME.jsonl" > "$RUN/$NAME.md"
rm "$RUN/prompt.txt"
if diff -r -x .claude -x .git "$H/hw7-heist" "$T" > "$RUN/$NAME.integrity.txt"; then
  echo "No files modified: target is byte-identical to the original HW7 project (excluding the installed .claude/skills)." > "$RUN/$NAME.integrity.txt"
fi
