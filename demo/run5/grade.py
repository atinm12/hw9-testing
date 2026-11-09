"""Grade run #5 trigger cases: did the checker skill fire exactly when expected, with no bad skill names?"""
import json, sys
from pathlib import Path
here = Path(__file__).parent
rows, misfires = [], 0
for line in open(here / "cases.tsv"):
    cid, expected, prompt = line.rstrip("\n").split("\t")
    skills, avail, first = [], [], None
    for l in open(here / f"{cid}.jsonl"):
        e = json.loads(l)
        if e.get("type") == "system" and e.get("subtype") == "init":
            avail = e.get("skills", [])
        if e.get("type") == "assistant":
            for c in e["message"]["content"]:
                if c["type"] == "tool_use":
                    first = first or c["name"]
                    if c["name"] == "Skill":
                        skills.append(c["input"].get("skill"))
    fired = "verify-readme-skill" in skills
    bad_names = [s for s in skills if s not in avail]
    ok = (fired == (expected == "yes")) and not bad_names
    misfires += not ok
    rows.append(f"| {cid} | {prompt} | {'trigger' if expected == 'yes' else 'no trigger'} | {', '.join(skills) or '—'} | {first or '—'} | {'✅' if ok else '❌'} |")
print("| Case | Prompt | Expected | Skills invoked | First tool | OK |\n|---|---|---|---|---|---|")
print("\n".join(rows))
print(f"\nMisfires: {misfires} / {len(rows)}")
