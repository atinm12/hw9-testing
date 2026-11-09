"""Sample application used to test verify_readme_claims."""

from utils.helpers import format_name


def greet(name: str) -> str:
    """Return a greeting for the given name."""
    return f"Hello, {format_name(name)}!"


if __name__ == "__main__":
    print(greet("world"))
