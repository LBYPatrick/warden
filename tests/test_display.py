"""Tests for warden.display module."""

from unittest.mock import patch

from warden.display import _NC, _c, bold, dim, green, red


class TestColorOutput:
    def test_tty_includes_ansi(self):
        with patch("warden.display._is_tty", return_value=True):
            result = green("hello")
            assert "\033[" in result
            assert "hello" in result
            assert result.endswith(_NC)

    def test_non_tty_strips_ansi(self):
        with patch("warden.display._is_tty", return_value=False):
            result = green("hello")
            assert result == "hello"

    def test_bold(self):
        with patch("warden.display._is_tty", return_value=True):
            result = bold("test")
            assert "test" in result

    def test_dim(self):
        with patch("warden.display._is_tty", return_value=True):
            result = dim("test")
            assert "test" in result

    def test_red(self):
        with patch("warden.display._is_tty", return_value=False):
            assert red("error") == "error"

    def test_c_helper_non_tty(self):
        with patch("warden.display._is_tty", return_value=False):
            assert _c("\033[0;32m", "text") == "text"
