"""Tests for warden.scanner module."""

from warden.platform_info import Platform, detect_platform
from warden.scanner import list_tools, scan_tools


class TestPlatformDetection:
    def test_detects_platform(self):
        platform = detect_platform()
        assert platform in (Platform.MACOS, Platform.LINUX)


class TestScanTools:
    def test_returns_list_of_strings(self):
        platform = detect_platform()
        tools = scan_tools(platform)
        assert isinstance(tools, list)
        for t in tools:
            assert isinstance(t, str)

    def test_results_are_sorted(self):
        platform = detect_platform()
        tools = scan_tools(platform)
        assert tools == sorted(tools)


class TestListTools:
    def test_returns_tuples(self):
        platform = detect_platform()
        result = list_tools(platform)
        assert isinstance(result, list)
        for slug, name, installed in result:
            assert isinstance(slug, str)
            assert isinstance(name, str)
            assert isinstance(installed, bool)
