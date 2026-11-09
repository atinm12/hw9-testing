#!/bin/zsh
# Demo run #4: triggering + output-format test. Usage: command.sh <label> <target-dir> <prompt>
D=${0:A:h:h}; LABEL=$1; TARGET=$2; PROMPT=$3
echo "$PROMPT" > "$D/run4/$LABEL.prompt.txt"
cd "$D/$TARGET" && ~/.local/bin/claude -p "$PROMPT" \
  --output-format stream-json --verbose --setting-sources project \
  --strict-mcp-config --mcp-config "$D/mcp-config.json" \
  --permission-mode dontAsk \
  --allowedTools "Skill mcp__verify-readme-claims__verify_readme_claims Read Grep Glob Edit Write Bash(python3:*) Bash(ls:*) Bash(find:*) Bash(grep:*) Bash(cat:*)" \
  --max-turns ${MAXTURNS:-40} < /dev/null > "$D/run4/$LABEL.jsonl"
