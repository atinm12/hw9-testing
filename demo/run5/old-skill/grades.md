| Case | Prompt | Expected | Skills invoked | First tool | OK |
|---|---|---|---|---|---|
| P1 | Are the docs in this project still in sync with the code? | trigger | verify-readme-skill | Skill | ✅ |
| P2 | I'm about to tag v1.0. Is anything in the project documentation out of date with the implementation? | trigger | verify-readme-claims, verify-readme-skill | Skill | ❌ |
| P3 | Someone filed an issue saying the quickstart instructions don't work. Can you figure out what's wrong with them? | trigger | — | Bash | ❌ |
| P4 | Double-check the README before I open this PR. | trigger | verify-readme-skill | Skill | ✅ |
| P5 | Fact-check README.md against the source. | trigger | verify-readme-skill | Skill | ✅ |
| N1 | What does pipeline.py do? Answer in two sentences. | no trigger | — | Bash | ✅ |
| N2 | Write a README for the api/ folder. | no trigger | readme-writer | Skill | ✅ |
| N3 | Fix the typos and grammar in README.md. | no trigger | — | Read | ✅ |
| N4 | Add a docstring to get_vs_similar_teams in features/matchup_features.py. | no trigger | — | Bash | ✅ |

Misfires: 2 / 9
