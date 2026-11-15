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

import logging
import os
import sys
import time
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# All parsing, indexing and verification logic lives in claims.py, which has no
# MCP dependency and can be imported and tested on its own.
from claims import _format_report, extract_claims, scan_project, verify_claims

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
