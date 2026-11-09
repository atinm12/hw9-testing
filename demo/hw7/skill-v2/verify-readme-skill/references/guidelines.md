# Cross-referencing README claims against Python source

How to decide whether something a README says about a Python project is actually true in the code. Apply these rules to every claim, whether the `verify_readme_claims` tool found it or you're checking by hand.

## 1. Identify the claim type

| README text | Claim type | Example |
|---|---|---|
| A path with an extension or trailing `/` | File / directory | `src/app.py`, `config/` |
| Dotted name without parentheses, used as an import | Module | `mypkg.utils`, `python -m mypkg.cli` |
| Name followed by `()` | Function or class call | `load_config()`, `Parser()` |
| `Name.attr()` | Method or module function | `Parser.parse()`, `utils.slugify()` |
| `from X import Y` / `import X` in a code block | Import (module + name) | `from mypkg import Client` |
| Call with arguments in a code block | Signature | `connect(host, port=5432)` |

Skip URLs, shell commands (`pip`, `git`, `npm`), absolute paths, placeholders (`<your_file>`, `your_module.py`), and Python built-ins (`print()`, `open()`).

## 2. Files and directories

1. Resolve relative to the **project root** first, then relative to the **README's own folder**. Links in a nested README (e.g. `docs/README.md`) are usually relative to that README.
2. Treat paths as **case-sensitive**. `App.py` and `app.py` are different on Linux, even though macOS treats them as the same.
3. If the path doesn't exist but a file with the same name exists elsewhere, classify it as **wrong location**, not valid, and report the real path.
4. Ignore anything under `.venv/`, `venv/`, `site-packages/`, `__pycache__/`, `build/`, `dist/`, `.git/`. Code there isn't part of the project.
5. Files created by setup steps (`.env`, `*.db`, build output) or listed in `.gitignore` are **expected missing**, not errors.

## 3. Modules

A module claim `a.b.c` is valid if any of these exist, checked in order:

- `a/b/c.py`
- `a/b/c/__init__.py`
- the same under `src/` (the "src layout": `src/a/b/c.py`)

Every parent package must also be importable (`a/__init__.py`, `a/b/__init__.py`), unless the project deliberately uses namespace packages with no `__init__.py`. For `python -m pkg`, also require `pkg/__main__.py`.

## 4. Functions, classes and methods

Find definitions by **parsing** the source, not by text search. A grep for `def load` also matches comments, strings and `def load_all`.

```bash
python3 -c "import ast,sys; [print(n.lineno, type(n).__name__, n.name) for n in ast.walk(ast.parse(open(sys.argv[1]).read())) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]" path/to/file.py
```

For JavaScript and other languages there is no parser to hand, so search for the definition forms and open the match: `function name(`, `name(...) {` and `name: function` inside object literals, `name = (...) =>`, and `Namespace.name = function`.

Rules:

- **Functions:** match `def name` and `async def name`. Functions nested inside another function aren't reachable by users; count them only if the README is describing internals.
- **Classes:** `Parser()` is satisfied by `class Parser`. Constructor arguments are checked against `__init__` (or the fields of a `@dataclass`).
- **Methods:** `Parser.parse()` requires a `parse` defined *in the body of* `class Parser`, or inherited from one of its base classes in the project. A top-level `parse` function somewhere else doesn't count; classify it as **wrong location**.
- **Module-qualified names:** for `utils.slugify()`, check that `slugify` is defined in the `utils` module specifically, not just anywhere.
- **Other definitions that count:**
  - `name = lambda ...` and `name = functools.partial(...)` at module level
  - `@property` (README may show it without `()`)
  - `@staticmethod` / `@classmethod`
  - functions defined under `if TYPE_CHECKING:` or `try/except ImportError:` (check both branches)

## 5. Imports and re-exports

For `from mypkg import Client`, the name doesn't have to be *defined* in `mypkg/__init__.py`. It only has to be *importable* from there. Valid if `mypkg/__init__.py` does one of:

- defines `Client` directly
- imports it: `from .client import Client` or `from mypkg.client import *`
- lists it in `__all__` and imports it

If `Client` is defined in `mypkg/client.py` but `__init__.py` doesn't import it, the README's import line would fail. Classify it as **wrong location** and suggest `from mypkg.client import Client`.

For an `import *` chain, follow it one level. If the target module defines `__all__`, the name must be in it.

## 6. Signatures

When the README shows a call with arguments, compare it to the definition:

- **Required parameters:** every parameter without a default must be supplied, positionally or by keyword.
- **Keyword arguments:** each `name=` in the README must be a real parameter, unless the function accepts `**kwargs`.
- **Positional count:** no more positional arguments than the function accepts, unless it has `*args`.
- **Methods:** don't count `self` / `cls`.
- **Return values:** if the README says "returns a dict" and the function has a return annotation, check it. Without an annotation, read the `return` statements. Note uncertainty rather than guess.

A name that exists with an incompatible signature is a **signature mismatch**. Report it separately from "missing".

## 7. Things static analysis can't verify

Mark these **unverifiable** (not missing) and say why:

- names created dynamically: `setattr(module, ...)`, `globals()[name] = ...`, `__getattr__` on a module
- functions registered by plugins, entry points (`pyproject.toml` `[project.scripts]`) or decorators that rename them
- code in C extensions (`.so`, `.pyd`) or generated at build time

For CLI commands the README says are installed (e.g. `mytool run`), check `[project.scripts]` in `pyproject.toml` or `entry_points` in `setup.py`/`setup.cfg`, then confirm the target `module:function` exists.

## 7b. Commands, flags, environment variables, dependencies and counts

The checker tool ignores these, so check each one by hand:

- **CLI flags** (`python pipeline.py --quick`): find the `argparse` `add_argument`, `click.option`, `sys.argv` check or equivalent in that script. A flag the parser doesn't define is `[NOT MET]`; give the real flag as the fix.
- **Environment variables** (`NEWS_API_KEY`): grep for `os.environ`, `os.getenv`, `process.env` and the variable name. Listed in `.env.example` but never read by code means `[NOT MET]`.
- **Dependencies and tech-stack claims** ("uses LightGBM", "Plotly dashboard"): the package must be in `requirements.txt` / `pyproject.toml` / `package.json` **and** imported somewhere. Listed but never imported means `[PARTIAL]`; neither means `[NOT MET]`.
- **Counts and numbers** ("75 tests", "three levels", "12 second cooldown"): count or look up the actual value and give it in the fix.
- **Commands** (`zsh test/run.sh`, `uvicorn api.main:app`): the script or `module:object` must exist. Don't run commands that start servers, install packages or take a long time.

## 8. Tests and private names

- A function defined **only in tests** (`tests/`, `test_*.py`, `conftest.py`) does not satisfy a README claim about the project's API.
- Names starting with `_` are private. If the README tells users to call one, flag it as a docs issue even though it exists.

## 9. Classifications for the report

| Classification | Meaning | Report it? |
|---|---|---|
| **Valid** | Exists at the stated location, signature compatible | No (count only) |
| **Wrong location** | Exists, but not where the README says | Yes, with the real location |
| **Signature mismatch** | Exists, but the README's call wouldn't work | Yes, with the real signature |
| **Missing** | Not found anywhere in the project | Yes; suggest the closest existing name if one is similar |
| **Expected missing** | Generated, gitignored or created by setup | Brief mention |
| **External** | Belongs to a third-party library or the standard library | No |
| **Example / placeholder** | Illustrative, not meant to exist | No; list in one line so the user can disagree |
| **Unverifiable** | Dynamic or generated; can't be checked statically | Yes, with the reason |

Always include the README line number and, for anything found, the `file:line` of the definition.

**Mapping to report statuses** (the format in `SKILL.md`):

| Classification | Status |
|---|---|
| Valid | `[MET]` |
| Wrong location, Signature mismatch, partly implemented | `[PARTIAL]` |
| Missing | `[NOT MET]` |
| Expected missing, External, Example / placeholder, Unverifiable | no status: list under **Skipped** with the reason |
