"""Unit tests for the pure logic in claims.py (no MCP, no server)."""

from pathlib import Path

import pytest

from claims import (
    Claim,
    ProjectIndex,
    _is_path_candidate,
    _looks_like_file,
    _resolve_function_claim,
    _resolve_path_claim,
    extract_claims,
)


def triples(claims):
    """Reduce claims to (kind, name, line) so whole lists can be compared exactly."""
    return [(c.kind, c.name, c.line) for c in claims]


# --------------------------------------------------------------------------- #
# _looks_like_file: decides whether a token names a file
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("token", ["Makefile", "LICENSE", ".gitignore", ".env.example", "docs/Dockerfile"])
def test_looks_like_file_accepts_bare_names_and_dotfiles(token):
    assert _looks_like_file(token) is True


@pytest.mark.parametrize("token", ["server.py", "src/App.TSX", "requirements.txt", "app.py/"])
def test_looks_like_file_accepts_known_extensions_case_insensitively(token):
    assert _looks_like_file(token) is True


@pytest.mark.parametrize("token", ["v1.2", "notes", "src/", "setup.exe", "", ".", "..", "../"])
def test_looks_like_file_rejects_versions_dirs_unknown_extensions_and_empty(token):
    assert _looks_like_file(token) is False


# --------------------------------------------------------------------------- #
# _is_path_candidate: filters out things that can't be local paths
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("token", ["src/app.py", "utils/helpers.py", "README.md", "a-b_c.d"])
def test_is_path_candidate_accepts_relative_paths(token):
    assert _is_path_candidate(token) is True


@pytest.mark.parametrize(
    "token",
    ["", "https://example.com/a.py", "#install", "mailto:me@x.com", "@mcp.tool",
     "$HOME", "~/notes.md", "/etc/hosts"],
)
def test_is_path_candidate_rejects_urls_anchors_and_absolute_paths(token):
    assert _is_path_candidate(token) is False


@pytest.mark.parametrize("token", ["my file.py", "a,b.py", "f(x)", "x=1", "*.py", "a;b", "[x]"])
def test_is_path_candidate_rejects_forbidden_characters(token):
    assert _is_path_candidate(token) is False


# --------------------------------------------------------------------------- #
# extract_claims: turns README text into file / directory / function claims
# --------------------------------------------------------------------------- #
def test_extract_claims_reads_inline_code_spans():
    readme = (
        "# Title\n"
        "Run `server.py` and see `utils/`.\n"
        "Call `verify_claims()` or `pkg.mod.run()`.\n"
        "Builtins like `print()` and decorators like `@mcp.tool()` are not claims.\n"
        "Commands with spaces such as `pip install x` are skipped.\n"
    )
    assert triples(extract_claims(readme)) == [
        ("file", "server.py", 2),
        ("directory", "utils", 2),
        ("function", "verify_claims", 3),
        ("function", "pkg.mod.run", 3),
    ]


def test_extract_claims_in_code_fence_takes_files_and_defs_but_not_comments():
    readme = (
        "intro\n"
        "```bash\n"
        "python server.py  # see notes.md for details\n"
        "def helper(x):\n"
        "cd src/\n"
        "```\n"
    )
    assert triples(extract_claims(readme)) == [
        ("file", "server.py", 3),
        ("function", "helper", 4),
    ]


def test_extract_claims_reports_each_name_once_at_its_first_line():
    readme = "`app.py` first\nthen `app.py` again\nand [link](app.py)\n"
    assert triples(extract_claims(readme)) == [("file", "app.py", 1)]


def test_extract_claims_markdown_links_strip_dot_slash_and_anchor_and_skip_remote():
    readme = (
        "[guide](docs/guide.md)\n"
        "[setup](./README.md#setup)\n"
        "[site](https://example.com/a.py)\n"
        "[top](#install)\n"
        "[mail](mailto:a@b.com)\n"
    )
    assert triples(extract_claims(readme)) == [
        ("file", "docs/guide.md", 1),
        ("file", "README.md", 2),
    ]


def test_extract_claims_ignores_paths_inside_ignored_directories():
    readme = "Use `.venv/bin/python` and `node_modules/x.js`, then `src/main.py`.\n"
    assert triples(extract_claims(readme)) == [("file", "src/main.py", 1)]


def test_extract_claims_unclosed_fence_treats_rest_as_code():
    readme = "`before.py`\n```\n`after_call()` is in the fence now\n"
    # The inline span after the unclosed fence must not become a function claim.
    assert triples(extract_claims(readme)) == [("file", "before.py", 1)]


@pytest.mark.parametrize("readme", ["", "\n\n", "Just prose, no code at all.\n"])
def test_extract_claims_returns_empty_list_when_nothing_to_claim(readme):
    assert extract_claims(readme) == []


# --------------------------------------------------------------------------- #
# _resolve_function_claim: looks a function claim up in the symbol index
# --------------------------------------------------------------------------- #
def index_with(symbols):
    return ProjectIndex(root=Path("."), symbols=symbols)


def test_resolve_function_exact_match_has_no_note():
    claim = Claim(kind="function", name="scan_project", line=1)
    _resolve_function_claim(claim, index_with({"scan_project": ["claims.py:10 (function)"]}))
    assert (claim.found, claim.locations, claim.note) == (True, ["claims.py:10 (function)"], "")


def test_resolve_function_falls_back_to_class_method_before_bare_name():
    claim = Claim(kind="function", name="pkg.Index.warn", line=1)
    idx = index_with({"Index.warn": ["a.py:5 (method)"], "warn": ["b.py:9 (function)"]})
    _resolve_function_claim(claim, idx)
    assert claim.found is True
    assert claim.locations == ["a.py:5 (method)"]
    assert claim.note == "matched as `Index.warn`"


def test_resolve_function_falls_back_to_bare_name():
    claim = Claim(kind="function", name="server.verify_claims", line=1)
    _resolve_function_claim(claim, index_with({"verify_claims": ["claims.py:20 (function)"]}))
    assert claim.found is True
    assert claim.locations == ["claims.py:20 (function)"]
    assert claim.note == "matched as `verify_claims`"


def test_resolve_function_missing_symbol_stays_not_found():
    claim = Claim(kind="function", name="does_not_exist", line=1)
    _resolve_function_claim(claim, index_with({"something_else": ["x.py:1 (function)"]}))
    assert (claim.found, claim.locations, claim.note) == (False, [], "")


# --------------------------------------------------------------------------- #
# _resolve_path_claim: looks a file / directory claim up in a real temp tree
# --------------------------------------------------------------------------- #
@pytest.fixture
def tree(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n")
    (tmp_path / "docs").mkdir()
    index = ProjectIndex(
        root=tmp_path.resolve(),
        files={"src/app.py"},
        dirs={"src", "docs"},
        by_basename={"app.py": ["src/app.py"]},
    )
    return tmp_path.resolve(), index


def test_resolve_path_found_at_stated_path(tree):
    root, index = tree
    claim = Claim(kind="file", name="src/app.py", line=1)
    _resolve_path_claim(claim, index, root)
    assert (claim.found, claim.locations, claim.note) == (True, ["src/app.py"], "")


def test_resolve_path_found_by_name_elsewhere_gets_note(tree):
    root, index = tree
    claim = Claim(kind="file", name="lib/app.py", line=1)
    _resolve_path_claim(claim, index, root)
    assert claim.found is True
    assert claim.locations == ["src/app.py"]
    assert claim.note == "not at the stated path, but found by name"


def test_resolve_path_missing_file_and_wrong_kind_are_not_found(tree):
    root, index = tree
    missing = Claim(kind="file", name="nope.py", line=1)
    _resolve_path_claim(missing, index, root)
    assert (missing.found, missing.locations) == (False, [])
    # "src/app.py" exists, but as a file: a directory claim for it must not match.
    wrong_kind = Claim(kind="directory", name="src/app.py", line=2)
    _resolve_path_claim(wrong_kind, index, root)
    assert wrong_kind.found is False


def test_resolve_path_outside_project_root_is_not_found(tree):
    root, index = tree
    claim = Claim(kind="file", name="../outside.py", line=1)
    (root.parent / "outside.py").write_text("")
    _resolve_path_claim(claim, index, root)
    assert claim.found is False
