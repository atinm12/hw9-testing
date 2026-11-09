"""Run verify_readme_claims against tests/sample_project and check the result.

Usage (from the project root, with the venv active):
    python tests/run_sample.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server import verify_readme_claims  # noqa: E402

SAMPLE = ROOT / "tests" / "sample_project"

EXPECTED_VALID = ["`app.py`", "`greet`", "`format_name`", "`utils/helpers.py`"]
EXPECTED_MISSING = ["`calculate_total`"]


def main() -> int:
    report = verify_readme_claims(str(SAMPLE), "README.md")
    print(report)

    valid_section, _, missing_section = report.partition("## ❌ Missing claims")
    failures = [f"expected VALID: {c}" for c in EXPECTED_VALID if c not in valid_section]
    failures += [f"expected MISSING: {c}" for c in EXPECTED_MISSING if c not in missing_section]

    if failures:
        print("FAIL\n  " + "\n  ".join(failures))
        return 1
    print(f"PASS: {len(EXPECTED_VALID)} valid and {len(EXPECTED_MISSING)} missing claims detected as expected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
