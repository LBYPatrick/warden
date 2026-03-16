"""Sheriff-style ANSI terminal output for Warden."""

import sys


def _is_tty() -> bool:
    return sys.stdout.isatty()


# ANSI color codes
_GREEN = "\033[0;32m"
_RED = "\033[0;31m"
_YELLOW = "\033[0;33m"
_BLUE = "\033[0;34m"
_CYAN = "\033[0;36m"
_BOLD = "\033[1m"
_DIM = "\033[2m"
_NC = "\033[0m"


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI color, stripping codes if not a TTY."""
    if not _is_tty():
        return text
    return f"{code}{text}{_NC}"


def green(text: str) -> str:
    return _c(_GREEN, text)


def red(text: str) -> str:
    return _c(_RED, text)


def yellow(text: str) -> str:
    return _c(_YELLOW, text)


def blue(text: str) -> str:
    return _c(_BLUE, text)


def cyan(text: str) -> str:
    return _c(_CYAN, text)


def bold(text: str) -> str:
    return _c(_BOLD, text)


def dim(text: str) -> str:
    return _c(_DIM, text)


def success(msg: str) -> None:
    """Print success message with green checkmark."""
    print(f"  {green('✓')} {msg}")


def error(msg: str) -> None:
    """Print error message with red cross."""
    print(f"  {red('✗')} {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    """Print warning message with yellow warning sign."""
    print(f"  {yellow('⚠')} {msg}")


def info(msg: str) -> None:
    """Print info message with blue play indicator."""
    print(f"  {blue('▶')} {msg}")


def item(msg: str) -> None:
    """Print list item with filled circle."""
    print(f"  {green('◉')} {msg}")


def skip(msg: str) -> None:
    """Print skipped item with circled slash."""
    print(f"  {yellow('⊘')} {msg}")


def header(title: str) -> None:
    """Print a bold section header."""
    print(f"\n{bold(title)}")


def kv(key: str, value: str) -> None:
    """Print a key-value pair."""
    print(f"  {dim(key + ':')} {value}")
