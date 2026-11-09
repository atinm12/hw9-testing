#!/bin/zsh
# Reproduces demo run #1. Run from the 114HW8/demo folder.
D=${0:A:h:h}
cd "$D/nba-predictor-drifted" && ~/.local/bin/claude -p "$(cat "$D/run1/prompt.txt")" \
  --output-format stream-json --verbose --setting-sources project \
  --strict-mcp-config --mcp-config "$D/mcp-config.json" \
  --permission-mode dontAsk --allowedTools "mcp__verify-readme-claims__verify_readme_claims Read Grep Glob" \
  --max-turns 20 < /dev/null > "$D/run1/transcript.jsonl"
python3 "$D/render_transcript.py" "$D/run1/transcript.jsonl" > "$D/run1/transcript.md"
