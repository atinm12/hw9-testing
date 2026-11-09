#!/bin/zsh
# Usage: run_case.sh <id> <max_turns> <prompt>   — fresh target copy per case, both skills installed.
D=${0:A:h:h}; SKILL_SRC=${SKILL_SRC:-$D/../verify-readme-skill}; OUT=${OUT:-$D/run5}; ID=$1; MT=$2; PROMPT=$3; T="$OUT/targets/$ID"
rm -rf "$T" && mkdir -p "$OUT/targets" && cp -R "$D/nba-predictor-drifted-v2" "$T" && mkdir -p "$T/.claude/skills"
cp -R "$SKILL_SRC" "$D/run5/decoy/readme-writer" "$T/.claude/skills/"
cd "$T" && ~/.local/bin/claude -p "$PROMPT" \
  --output-format stream-json --verbose --setting-sources project \
  --strict-mcp-config --mcp-config "$D/mcp-config.json" --permission-mode dontAsk \
  --allowedTools "Skill mcp__verify-readme-claims__verify_readme_claims Read Grep Glob Edit Write Bash(python3:*) Bash(ls:*) Bash(find:*) Bash(grep:*) Bash(cat:*)" \
  --max-turns $MT < /dev/null > "$OUT/$ID.jsonl"
