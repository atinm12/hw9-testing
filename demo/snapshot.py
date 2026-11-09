"""Fingerprint every file under a folder, or compare two fingerprints.

    python demo/snapshot.py take <root> <out.json> [--exclude DIR ...]
    python demo/snapshot.py diff <before.json> <after.json>

`diff` exits 1 if anything was added, removed or changed.
"""

import hashlib
import json
import os
import sys
from pathlib import Path

ALWAYS_SKIP = {".venv", ".git"}


def take(root: Path, out: Path, excludes: list[str]) -> None:
    root = root.resolve()
    skip = {(root / e).resolve() for e in excludes}
    files = {}
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in ALWAYS_SKIP and (here / d).resolve() not in skip)
        for name in sorted(filenames):
            path = here / name
            if path.is_symlink():
                files[path.relative_to(root).as_posix()] = "symlink:" + os.readlink(path)
                continue
            st = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            files[path.relative_to(root).as_posix()] = f"{digest} {st.st_mode:o}"
    out.write_text(json.dumps({"root": str(root), "files": files}, indent=1))
    print(f"snapshot: {len(files)} files under {root} -> {out}")


def diff(before_path: Path, after_path: Path) -> int:
    before = json.loads(before_path.read_text())["files"]
    after = json.loads(after_path.read_text())["files"]
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    print(f"compared {len(before)} -> {len(after)} files")
    for label, items in (("ADDED", added), ("REMOVED", removed), ("CHANGED", changed)):
        for p in items:
            print(f"  {label:8s} {p}")
    if not (added or removed or changed):
        print("  no differences: every file is byte-identical")
        return 0
    return 1


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "take":
        excl = sys.argv[sys.argv.index("--exclude") + 1:] if "--exclude" in sys.argv else []
        take(Path(sys.argv[2]), Path(sys.argv[3]), excl)
    elif len(sys.argv) == 4 and sys.argv[1] == "diff":
        sys.exit(diff(Path(sys.argv[2]), Path(sys.argv[3])))
    else:
        sys.exit(__doc__)
