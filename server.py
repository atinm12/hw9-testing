"""verify-readme-claims MCP server.

Exposes one tool, ``verify_readme_claims``, that checks whether the files,
directories and functions a README mentions actually exist in a project.

Built on the MCP Python SDK 2.x, where FastMCP was renamed to ``MCPServer``.

Run over stdio:        python server.py
Interactive testing:   mcp dev server.py
Verbose logging:       LOG_LEVEL=DEBUG python server.py

stdout carries the MCP JSON-RPC stream over stdio, so this module never
writes to it: all logging goes to stderr. Never use print() here.
"""

from __future__ import annotations

import ast
import builtins
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# --------------------------------------------------------------------------- #
# Logging: stderr only, so the JSON-RPC stream on stdout stays clean.
# --------------------------------------------------------------------------- #
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    stream=sys.stderr,
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    force=True,  # replace any handler a dependency may have pointed at stdout
)
logging.captureWarnings(True)  # route warnings.warn() through logging (stderr)
logger = logging.getLogger("verify-readme-claims")

mcp = MCPServer("verify-readme-claims")

MAX_README_BYTES = 5 * 1024 * 1024  # refuse to parse READMEs larger than 5 MB

# Directories that are never part of the project's own source.
IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "__pycache__", "node_modules",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".idea", ".vscode",
    "dist", "build", ".next", "target",
}

# Extensions that make an inline-code token look like a file path.
FILE_EXTENSIONS = {
    "py", "pyi", "ipynb", "js", "jsx", "ts", "tsx", "mjs", "cjs", "json", "yaml",
    "yml", "toml", "ini", "cfg", "conf", "env", "txt", "md", "rst", "csv", "tsv",
    "html", "css", "scss", "sh", "bash", "zsh", "ps1", "bat", "sql", "xml", "lock",
    "go", "rs", "java", "kt", "c", "h", "cpp", "hpp", "cs", "rb", "php", "swift",
    "r", "jl", "lua", "dart", "scala", "png", "jpg", "jpeg", "gif", "svg", "pdf",
    "example", "sample", "template", "dockerfile",
}

# Extensionless file names that are still clearly files.
KNOWN_BARE_FILES = {
    "Dockerfile", "Makefile", "Procfile", "LICENSE", "Gemfile", "Rakefile",
    "Vagrantfile", "Jenkinsfile",
}

# Regexes for finding function/class definitions in non-Python source files.
DEFINITION_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s+([A-Za-z_$][\w$]*)", re.M),
    re.compile(r"^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>", re.M),
    re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+([A-Za-z_$][\w$]*)", re.M),
    re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+([A-Za-z_]\w*)", re.M),  # Rust
    re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_]\w*)", re.M),  # Go
    re.compile(r"^\s*def\s+(?:self\.)?([A-Za-z_]\w*[?!]?)", re.M),  # Ruby
    re.compile(r"^\s*(?:public|private|protected|static|final|\s)+[\w<>\[\],\s]+\s+([A-Za-z_]\w*)\s*\([^;]*\)\s*\{", re.M),  # Java/C#/C++
]
SOURCE_EXTENSIONS = {
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".rs", ".go", ".rb",
    ".java", ".kt", ".cs", ".c", ".h", ".cpp", ".hpp", ".swift", ".php", ".scala",
}

INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FUNC_CALL_RE = re.compile(r"^([A-Za-z_][\w.]*)\s*\([^()]*\)$")
DEF_IN_README_RE = re.compile(r"^(?:async\s+)?(?:def|function|fn|func)\s+([A-Za-z_]\w*)")
PATH_TOKEN_RE = re.compile(r"(?<![\w/.-])((?:\.{0,2}/)?[\w.-]+(?:/[\w.-]+)*/?)(?![\w/-])")
FENCE_RE = re.compile(r"^\s*(```|~~~)")

BUILTIN_NAMES = set(dir(builtins))


@dataclass
class Claim:
    kind: str  # "file", "directory", or "function"
    name: str
    line: int
    found: bool = False
    locations: list[str] = field(default_factory=list)
    note: str = ""


@dataclass
class ProjectIndex:
    root: Path
    files: set[str] = field(default_factory=set)  # posix paths relative to root
    dirs: set[str] = field(default_factory=set)
    by_basename: dict[str, list[str]] = field(default_factory=dict)
    # symbol name -> list of "relative/path.py:line (kind)"
    symbols: dict[str, list[str]] = field(default_factory=dict)
    # Non-fatal problems (unreadable files, syntax errors) shown in the report.
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        logger.warning(message)
        self.warnings.append(message)


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
def _clean_path_arg(value: str, arg_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolError(f"`{arg_name}` must be a non-empty path string.")
    if "\x00" in value:
        raise ToolError(f"`{arg_name}` contains a null byte, which is not a valid path.")
    return value.strip()


def _validate_project_dir(project_path: str) -> Path:
    raw = _clean_path_arg(project_path, "project_path")
    try:
        root = Path(raw).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolError(f"Could not resolve project path `{raw}`: {exc}") from exc

    if not root.exists():
        if Path(raw).expanduser().is_symlink():
            raise ToolError(f"Project path `{raw}` is a broken symlink.")
        raise ToolError(f"Project directory `{raw}` does not exist (resolved to `{root}`).")
    if not root.is_dir():
        raise ToolError(f"Project path `{raw}` is a file, not a directory.")
    try:
        with os.scandir(root):
            pass
    except PermissionError as exc:
        raise ToolError(f"Permission denied reading project directory `{root}`.") from exc
    except OSError as exc:
        raise ToolError(f"Cannot open project directory `{root}`: {exc.strerror or exc}") from exc

    logger.debug("Project root resolved to %s", root)
    return root


def _validate_and_read_readme(readme_path: str, root: Path) -> tuple[Path, str]:
    raw = _clean_path_arg(readme_path, "readme_path")
    try:
        readme = Path(raw).expanduser()
        if not readme.is_absolute():
            readme = root / readme
        readme = readme.resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolError(f"Could not resolve README path `{raw}`: {exc}") from exc

    if not readme.exists():
        hint = ""
        try:
            candidates = sorted(p.name for p in root.iterdir() if p.name.lower().startswith("readme"))
        except OSError:
            candidates = []
        if candidates:
            hint = f" README-like files in the project root: {', '.join(candidates)}."
        raise ToolError(f"README `{raw}` does not exist (looked for `{readme}`).{hint}")
    if readme.is_dir():
        raise ToolError(f"README path `{raw}` is a directory, not a file.")
    if not readme.is_file():
        raise ToolError(f"README path `{raw}` is not a regular file.")

    try:
        size = readme.stat().st_size
    except OSError as exc:
        raise ToolError(f"Cannot stat README `{readme}`: {exc.strerror or exc}") from exc
    if size > MAX_README_BYTES:
        raise ToolError(
            f"README `{readme}` is {size / 1_048_576:.1f} MB, over the "
            f"{MAX_README_BYTES // 1_048_576} MB limit."
        )

    try:
        data = readme.read_bytes()
    except PermissionError as exc:
        raise ToolError(f"Permission denied reading README `{readme}`.") from exc
    except OSError as exc:
        raise ToolError(f"Could not read README `{readme}`: {exc.strerror or exc}") from exc

    if b"\x00" in data[:8192]:
        raise ToolError(f"README `{readme}` looks like a binary file, not text.")
    text = data.decode("utf-8", errors="replace")
    if "�" in text:
        logger.warning("README %s is not valid UTF-8; undecodable bytes were replaced", readme)
    if not text.strip():
        raise ToolError(f"README `{readme}` is empty.")

    try:
        readme.relative_to(root)
    except ValueError:
        logger.info("README %s is outside the project root %s", readme, root)

    logger.debug("Read README %s (%d bytes)", readme, size)
    return readme, text


# --------------------------------------------------------------------------- #
# Project scanning
# --------------------------------------------------------------------------- #
def _add_symbol(index: ProjectIndex, name: str, rel: str, line: int, kind: str) -> None:
    index.symbols.setdefault(name, []).append(f"{rel}:{line} ({kind})")


def _read_source(index: ProjectIndex, path: Path, rel: str) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        index.warn(f"{rel}: could not read ({exc.strerror or exc})")
        return None


def _index_python(index: ProjectIndex, path: Path, rel: str) -> None:
    text = _read_source(index, path, rel)
    if text is None:
        return
    try:
        tree = ast.parse(text, filename=rel)
    except SyntaxError as exc:
        index.warn(f"{rel}: syntax error, functions not indexed ({exc.msg}, line {exc.lineno})")
        return
    except (ValueError, RecursionError, MemoryError) as exc:
        index.warn(f"{rel}: could not parse ({type(exc).__name__}: {exc})")
        return
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _add_symbol(index, node.name, rel, node.lineno, "function")
        elif isinstance(node, ast.ClassDef):
            _add_symbol(index, node.name, rel, node.lineno, "class")
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _add_symbol(index, f"{node.name}.{item.name}", rel, item.lineno, "method")


def _index_other_source(index: ProjectIndex, path: Path, rel: str) -> None:
    text = _read_source(index, path, rel)
    if text is None:
        return
    for pattern in DEFINITION_PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            _add_symbol(index, match.group(1), rel, line, "definition")


def scan_project(root: Path) -> ProjectIndex:
    index = ProjectIndex(root=root)
    started = time.perf_counter()

    def on_walk_error(exc: OSError) -> None:
        where = exc.filename or "?"
        try:
            where = Path(where).relative_to(root).as_posix()
        except ValueError:
            pass
        index.warn(f"{where}: could not list directory ({exc.strerror or exc})")

    for dirpath, dirnames, filenames in os.walk(root, onerror=on_walk_error):
        skipped = [d for d in dirnames if d in IGNORED_DIRS]
        if skipped:
            logger.debug("Skipping ignored dirs in %s: %s", dirpath, ", ".join(skipped))
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)
        rel_dir = Path(dirpath).relative_to(root)
        for d in dirnames:
            index.dirs.add((rel_dir / d).as_posix())
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            rel = (rel_dir / fname).as_posix()
            index.files.add(rel)
            index.by_basename.setdefault(fname, []).append(rel)
            suffix = full.suffix.lower()
            if suffix == ".py":
                _index_python(index, full, rel)
            elif suffix in SOURCE_EXTENSIONS:
                _index_other_source(index, full, rel)

    logger.debug(
        "Scanned %s: %d files, %d dirs, %d symbols, %d warnings in %.3fs",
        root, len(index.files), len(index.dirs), len(index.symbols),
        len(index.warnings), time.perf_counter() - started,
    )
    return index


# --------------------------------------------------------------------------- #
# README parsing
# --------------------------------------------------------------------------- #
def _looks_like_file(token: str) -> bool:
    token = token.rstrip("/")
    name = token.rsplit("/", 1)[-1]
    if not name or name in {".", ".."}:
        return False
    if name in KNOWN_BARE_FILES:
        return True
    if re.fullmatch(r"\.[\w.-]+", name):  # dotfiles such as .gitignore, .env.example
        return True
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        return ext in FILE_EXTENSIONS
    return False


def _is_path_candidate(token: str) -> bool:
    if not token or "://" in token or token.startswith(("#", "mailto:", "@", "$", "~", "/")):
        return False
    if any(ch in token for ch in " {}<>|*?\"'=,;()[]\\"):
        return False
    return True


def extract_claims(readme_text: str) -> list[Claim]:
    claims: list[Claim] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, name: str, line: int) -> None:
        key = (kind, name)
        if key not in seen:
            seen.add(key)
            claims.append(Claim(kind=kind, name=name, line=line))
            logger.debug("Claim found: %s `%s` (line %d)", kind, name, line)

    def add_path(token: str, line: int, strict: bool) -> None:
        token = token.strip().split("#", 1)[0]
        if token.startswith("./"):
            token = token[2:]
        if not _is_path_candidate(token):
            return
        if token.split("/", 1)[0] in IGNORED_DIRS:  # .venv, .git, node_modules, ...
            return
        if token.endswith("/") and len(token) > 1:
            add("directory", token.rstrip("/"), line)
        elif _looks_like_file(token) or (not strict and "/" in token):
            add("file", token, line)

    in_fence = False
    for lineno, line in enumerate(readme_text.splitlines(), start=1):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue

        if in_fence:
            # Code blocks: only pick up tokens that clearly look like files
            # (e.g. `python server.py`, `pip install -r requirements.txt`).
            code_part = re.split(r"\s#\s|^\s*#\s", line, maxsplit=1)[0]  # drop shell comments
            for match in PATH_TOKEN_RE.finditer(code_part):
                token = match.group(1)
                if _looks_like_file(token) and not token.endswith("/"):
                    add_path(token, lineno, strict=True)
            stripped = line.strip()
            if m := DEF_IN_README_RE.match(stripped):
                add("function", m.group(1), lineno)
            continue

        # Markdown links to local targets are file/directory claims.
        for match in MD_LINK_RE.finditer(line):
            target = match.group(1)
            if "://" not in target and not target.startswith(("#", "mailto:")):
                add_path(target, lineno, strict=False)

        # Inline code spans.
        for match in INLINE_CODE_RE.finditer(line):
            code = match.group(1).strip()
            if code.startswith("@"):  # decorators such as @mcp.tool()
                continue
            if m := FUNC_CALL_RE.match(code):
                name = m.group(1)
                short = name.rsplit(".", 1)[-1]
                if short not in BUILTIN_NAMES:
                    add("function", name, lineno)
                continue
            if m := DEF_IN_README_RE.match(code):
                add("function", m.group(1), lineno)
                continue
            if " " not in code:
                add_path(code, lineno, strict=True)

    if in_fence:
        logger.warning("README has an unclosed code fence; the rest was parsed as code")
    logger.debug("Extracted %d claims from README", len(claims))
    return claims


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
def _resolve_path_claim(claim: Claim, index: ProjectIndex, readme_dir: Path) -> None:
    root = index.root
    pool = index.files if claim.kind == "file" else index.dirs

    # 1. Relative to the project root, then relative to the README's directory.
    for base in (root, readme_dir):
        candidate = (base / claim.name).resolve()
        try:
            rel = candidate.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel in pool or (claim.kind == "file" and candidate.is_file()) or (
            claim.kind == "directory" and candidate.is_dir()
        ):
            claim.found = True
            claim.locations = [rel]
            return

    # 2. Same name somewhere else in the tree.
    basename = claim.name.rstrip("/").rsplit("/", 1)[-1]
    if claim.kind == "file":
        matches = index.by_basename.get(basename, [])
    else:
        matches = sorted(d for d in index.dirs if d.rsplit("/", 1)[-1] == basename)
    if matches:
        claim.found = True
        claim.locations = matches
        claim.note = "not at the stated path, but found by name"


def _resolve_function_claim(claim: Claim, index: ProjectIndex) -> None:
    name = claim.name
    candidates = [name]
    parts = name.split(".")
    if len(parts) >= 2:
        candidates.append(".".join(parts[-2:]))  # Class.method
    candidates.append(parts[-1])  # bare function name
    for candidate in candidates:
        if candidate in index.symbols:
            claim.found = True
            claim.locations = index.symbols[candidate]
            if candidate != name:
                claim.note = f"matched as `{candidate}`"
            return


def verify_claims(claims: list[Claim], index: ProjectIndex, readme_dir: Path) -> None:
    for claim in claims:
        try:
            if claim.kind == "function":
                _resolve_function_claim(claim, index)
            else:
                _resolve_path_claim(claim, index, readme_dir)
        except (OSError, RuntimeError, ValueError) as exc:
            # One malformed claim (e.g. a path that is too long) must not sink the report.
            claim.found = False
            claim.note = f"could not be checked: {exc}"
            index.warn(f"README line {claim.line}: could not check `{claim.name}` ({exc})")
        logger.debug(
            "%s %s `%s` -> %s", "VALID" if claim.found else "MISSING",
            claim.kind, claim.name, ", ".join(claim.locations) or "-",
        )


def _format_report(
    readme_rel: str, project_root: Path, index: ProjectIndex, claims: list[Claim]
) -> str:
    valid = [c for c in claims if c.found]
    missing = [c for c in claims if not c.found]
    lines = [
        "# README Claim Verification Report",
        "",
        f"- **Project:** `{project_root}`",
        f"- **README:** `{readme_rel}`",
        f"- **Scanned:** {len(index.files)} files, {len(index.symbols)} distinct symbols",
        f"- **Claims checked:** {len(claims)}  |  **Valid:** {len(valid)}  |  **Missing:** {len(missing)}",
    ]
    if claims:
        lines.append(f"- **Accuracy:** {len(valid) / len(claims):.0%}")
    else:
        lines.append("- No file, directory or function claims were found in the README.")
    lines.append("")

    def section(title: str, items: list[Claim], show_locations: bool) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        if not items:
            lines.append("_None._")
            lines.append("")
            return
        for kind, heading in (("file", "Files"), ("directory", "Directories"), ("function", "Functions")):
            group = [c for c in items if c.kind == kind]
            if not group:
                continue
            lines.append(f"### {heading}")
            for c in group:
                entry = f"- `{c.name}` (README line {c.line})"
                if show_locations and c.locations:
                    shown = ", ".join(f"`{loc}`" for loc in c.locations[:3])
                    extra = f" +{len(c.locations) - 3} more" if len(c.locations) > 3 else ""
                    entry += f" → {shown}{extra}"
                if c.note:
                    entry += f" _({c.note})_"
                lines.append(entry)
            lines.append("")

    section("✅ Valid claims", valid, show_locations=True)
    section("❌ Missing claims", missing, show_locations=False)

    if index.warnings:
        lines.append(f"## ⚠️ Warnings ({len(index.warnings)})")
        lines.append("")
        lines.extend(f"- {w}" for w in index.warnings[:50])
        if len(index.warnings) > 50:
            lines.append(f"- … and {len(index.warnings) - 50} more (see server log)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# MCP tool
# --------------------------------------------------------------------------- #
@mcp.tool()
def verify_readme_claims(project_path: str, readme_path: str) -> str:
    """Check that files, directories and functions mentioned in a README exist in the project.

    Args:
        project_path: Path to the project's root directory.
        readme_path: Path to the README file. May be absolute or relative to project_path.

    Returns:
        A Markdown report listing valid claims (with where they were found) and
        missing claims (with the README line that made them). Invalid inputs,
        such as a missing directory or README, return an MCP error result.
    """
    logger.info("verify_readme_claims(project_path=%r, readme_path=%r)", project_path, readme_path)
    started = time.perf_counter()
    try:
        root = _validate_project_dir(project_path)
        readme, text = _validate_and_read_readme(readme_path, root)
        index = scan_project(root)
        claims = extract_claims(text)
        verify_claims(claims, index, readme.parent)
        try:
            readme_rel = readme.relative_to(root).as_posix()
        except ValueError:
            readme_rel = str(readme)
        report = _format_report(readme_rel, root, index, claims)
    except ToolError as exc:
        # Anticipated failure (bad input): the client gets is_error=True with this message.
        logger.error("verify_readme_claims failed: %s", exc)
        raise
    except Exception as exc:
        # Unexpected bug: log the full traceback to stderr, give the client a readable message.
        logger.exception("Unexpected error in verify_readme_claims")
        raise ToolError(f"Internal error while verifying README ({type(exc).__name__}): {exc}") from exc

    valid = sum(c.found for c in claims)
    logger.info(
        "Verified %d claims (%d valid, %d missing) in %.3fs",
        len(claims), valid, len(claims) - valid, time.perf_counter() - started,
    )
    return report


def main() -> None:
    logger.info("Starting verify-readme-claims MCP server (stdio, log level %s)", LOG_LEVEL)
    try:
        mcp.run()  # stdio transport
    except KeyboardInterrupt:
        logger.info("Interrupted, shutting down")
    except Exception:
        logger.exception("Server crashed")
        sys.exit(1)
    logger.info("Server stopped")


if __name__ == "__main__":
    main()
