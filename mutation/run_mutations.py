import subprocess, sys, re, json
M = [
 ("M1 flip extension check", "return ext in FILE_EXTENSIONS", "return ext not in FILE_EXTENSIONS"),
 ("M2 drop lower()", 'ext = name.rsplit(".", 1)[-1].lower()', 'ext = name.rsplit(".", 1)[-1]'),
 ("M3 allow absolute paths", 'token.startswith(("#", "mailto:", "@", "$", "~", "/"))', 'token.startswith(("#", "mailto:", "@", "$", "~"))'),
 ("M4 disable dedup", "        if key not in seen:", "        if True:"),
 ("M5 invert note condition", "if candidate != name:", "if candidate == name:"),
 ("M6 keep shell comments", 'code_part = re.split(r"\\s#\\s|^\\s*#\\s", line, maxsplit=1)[0]', "code_part = line"),
 ("M7 off-by-one ./ strip", "token = token[2:]", "token = token[1:]"),
 ("M8 ignored-dir check uses last segment", 'if token.split("/", 1)[0] in IGNORED_DIRS:', 'if token.split("/", 1)[-1] in IGNORED_DIRS:'),
 ("M9 file check ignores kind", 'if rel in pool or (claim.kind == "file" and candidate.is_file()) or (', 'if rel in pool or (candidate.is_file()) or ('),
 ("M10 claim builtins", "if short not in BUILTIN_NAMES:", "if True:"),
 ("M11 drop decorator skip", 'if code.startswith("@"):', 'if code.startswith("\\x00"):'),
 ("M12 line numbers from 0", "enumerate(readme_text.splitlines(), start=1)", "enumerate(readme_text.splitlines(), start=0)"),
 ("M13 drop bare-name fallback", "    candidates.append(parts[-1])  # bare function name", "    pass"),
 ("M14 drop . and .. guard", 'if not name or name in {".", ".."}:', "if not name:"),
 ("M15 drop rstrip in _looks_like_file", '    token = token.rstrip("/")\n    name = token.rsplit("/", 1)[-1]', '    name = token.rsplit("/", 1)[-1]'),
 ("M16 Class.method needs 3 parts", "if len(parts) >= 2:", "if len(parts) >= 3:"),
 ("M17 fence toggles only on open", "in_fence = not in_fence", "in_fence = True"),
 ("M18 skip bare files list", "if name in KNOWN_BARE_FILES:", "if name in set():"),
 ("M19 directory claims become files", 'add("directory", token.rstrip("/"), line)', 'add("file", token.rstrip("/"), line)'),
 ("M20 drop strict guard on links", 'elif _looks_like_file(token) or (not strict and "/" in token):', 'elif _looks_like_file(token):'),
]
orig = open("claims.py").read()
out = []
try:
    for name, old, new in M:
        assert orig.count(old) == 1, (name, orig.count(old))
        open("claims.py", "w").write(orig.replace(old, new))
        r = subprocess.run([".venv/bin/python", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_claims.py", "-rf", "--tb=line"], capture_output=True, text=True)
        failed = re.findall(r"^FAILED (\S+)", r.stdout, re.M)
        msgs = re.findall(r"^E\s+(.*)$|^(/\S+:\d+: .*)$", r.stdout, re.M)
        summary = r.stdout.strip().splitlines()[-1]
        out.append({"name": name, "old": old, "new": new, "failed": failed, "summary": summary, "stdout": r.stdout})
        print(f"{name}: {summary}")
        for f in failed[:4]: print("   ", f)
finally:
    open("claims.py", "w").write(orig)
json.dump(out, open(sys.argv[1], "w"), indent=1)
