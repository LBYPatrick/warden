"""Sheriff-style terminal output for Warden, powered by rich."""

import time
from contextlib import contextmanager

from rich.console import Console
from rich.rule import Rule

_BANNER_WIDTH = 43

_console = Console(highlight=False)
_err_console = Console(stderr=True, highlight=False)


# ---------------------------------------------------------------------------
# Color helpers (return styled strings for embedding in other output)
# ---------------------------------------------------------------------------


def green(text: str) -> str:
    return f"[green]{text}[/green]"


def red(text: str) -> str:
    return f"[red]{text}[/red]"


def yellow(text: str) -> str:
    return f"[yellow]{text}[/yellow]"


def blue(text: str) -> str:
    return f"[blue]{text}[/blue]"


def cyan(text: str) -> str:
    return f"[cyan]{text}[/cyan]"


def bold(text: str) -> str:
    return f"[bold]{text}[/bold]"


def dim(text: str) -> str:
    return f"[dim]{text}[/dim]"


# ---------------------------------------------------------------------------
# Output primitives
# ---------------------------------------------------------------------------


def success(msg: str) -> None:
    _console.print(f"  [green]✓[/green] {msg}")


def error(msg: str) -> None:
    _err_console.print(f"  [red]✗[/red] {msg}")


def warn(msg: str) -> None:
    _console.print(f"  [yellow]⚠[/yellow] {msg}")


def info(msg: str) -> None:
    _console.print(f"  [blue]▶[/blue] {msg}")


def item(msg: str) -> None:
    _console.print(f"  [green]◉[/green] {msg}")


def skip(msg: str) -> None:
    _console.print(f"  [yellow]⊘[/yellow] {msg}")


def header(title: str) -> None:
    _console.print(f"\n[bold]{title}[/bold]")


def step(current: int, total: int, title: str) -> None:
    _console.print(f"\n[bold]\\[{current}/{total}] {title}[/bold]")


def kv(key: str, value: str) -> None:
    _console.print(f"  [dim]{key}:[/dim] {value}")


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def banner(title: str) -> None:
    _console.print()
    _console.print(Rule(style="bold"))
    _console.print(f"[bold]{title}[/bold]", justify="center")
    _console.print(Rule(style="bold"))
    _console.print()


# ---------------------------------------------------------------------------
# Elapsed time
# ---------------------------------------------------------------------------


def format_elapsed(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m = s // 60
    s = s % 60
    return f"{m}m {s}s"


def success_timed(msg: str, elapsed: float) -> None:
    _console.print(f"  [green]✓[/green] {msg} [dim]({format_elapsed(elapsed)})[/dim]")


def error_timed(msg: str, elapsed: float) -> None:
    _err_console.print(f"  [red]✗[/red] {msg} [dim]({format_elapsed(elapsed)})[/dim]")


# ---------------------------------------------------------------------------
# Spinner context manager
# ---------------------------------------------------------------------------


@contextmanager
def spinner(description: str):
    """Context manager showing a spinner, then result with timing."""
    sp = _Spinner(description)
    sp.start()
    try:
        yield sp
    except Exception:
        sp.fail("exception")
        raise
    finally:
        if not sp._finished:
            sp.ok()


class _Spinner:
    def __init__(self, description: str):
        self.description = description
        self._start_time = 0.0
        self._finished = False

    def start(self):
        self._start_time = time.monotonic()
        if _console.is_terminal:
            _console.print(
                f"  [blue]◐[/blue] {self.description}...", end="", highlight=False
            )
        else:
            _console.print(f"  [blue]▶[/blue] {self.description}...")

    def ok(self, msg: str | None = None):
        elapsed = time.monotonic() - self._start_time
        self._finished = True
        label = msg or self.description
        if _console.is_terminal:
            _console.print(
                f"\r\033[K  [green]✓[/green] {label} [dim]({format_elapsed(elapsed)})[/dim]"
            )
        else:
            _console.print(
                f"  [green]✓[/green] {label} [dim]({format_elapsed(elapsed)})[/dim]"
            )

    def fail(self, msg: str | None = None):
        elapsed = time.monotonic() - self._start_time
        self._finished = True
        label = msg or f"{self.description} FAILED"
        if _console.is_terminal:
            _err_console.print(
                f"\r\033[K  [red]✗[/red] {label} [dim]({format_elapsed(elapsed)})[/dim]"
            )
        else:
            _err_console.print(
                f"  [red]✗[/red] {label} [dim]({format_elapsed(elapsed)})[/dim]"
            )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def summary(title: str, items: list[tuple[bool, str]]) -> bool:
    banner(title)
    all_ok = True
    for passed, label in items:
        if passed:
            success(label)
        else:
            error(label)
            all_ok = False
    _console.print()
    _console.print(Rule(style="bold"))
    _console.print()
    if all_ok:
        _console.print("[green bold]Complete![/green bold]")
    else:
        _err_console.print("[red bold]Completed with errors[/red bold]")
    return all_ok
