#!/bin/zsh
# Reproduces demo run #3 (skill + MCP tool, write tools allowed). Run from anywhere.
D=${0:A:h:h}; W=${D:h}
python3 "$D/snapshot.py" take "$W" "$D/run3/before.json" --exclude demo/run3
cd "$D/nba-predictor-run3" && ~/.local/bin/claude -p "$(cat "$D/run3/prompt.txt")" \
  --output-format stream-json --verbose --setting-sources project \
  --strict-mcp-config --mcp-config "$D/mcp-config.json" \
  --permission-mode dontAsk \
  --allowedTools "Skill mcp__verify-readme-claims__verify_readme_claims Read Grep Glob Edit Write Bash(python3:*) Bash(ls:*) Bash(find:*) Bash(grep:*) Bash(cat:*)" \
  --max-turns 40 < /dev/null > "$D/run3/transcript.jsonl"
python3 "$D/snapshot.py" take "$W" "$D/run3/after.json" --exclude demo/run3
python3 "$D/snapshot.py" diff "$D/run3/before.json" "$D/run3/after.json" | tee "$D/run3/file-integrity.txt"
python3 "$D/render_transcript.py" "$D/run3/transcript.jsonl" > "$D/run3/transcript.md"
