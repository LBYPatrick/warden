"""Tests for warden.display module."""

from warden.display import bold, dim, format_elapsed, green, red


class TestRichMarkup:
    def test_green(self):
        assert green("hello") == "[green]hello[/green]"

    def test_red(self):
        assert red("error") == "[red]error[/red]"

    def test_bold(self):
        assert bold("title") == "[bold]title[/bold]"

    def test_dim(self):
        assert dim("faded") == "[dim]faded[/dim]"


class TestFormatElapsed:
    def test_seconds(self):
        assert format_elapsed(5) == "5s"
        assert format_elapsed(0) == "0s"

    def test_minutes(self):
        assert format_elapsed(65) == "1m 5s"
        assert format_elapsed(120) == "2m 0s"
