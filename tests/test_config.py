"""Tests for warden.config module."""

import json

from warden.config import (
    find_target,
    resolve_config_path,
    resolve_ssh_command,
    serialize_config,
    strip_jsonc_comments,
)


class TestStripJsoncComments:
    def test_line_comments(self):
        text = '{\n  // comment\n  "key": "value"\n}'
        result = strip_jsonc_comments(text)
        assert json.loads(result) == {"key": "value"}

    def test_block_comments(self):
        text = '{\n  /* block */\n  "key": "value"\n}'
        result = strip_jsonc_comments(text)
        assert json.loads(result) == {"key": "value"}

    def test_multiline_block_comment(self):
        text = '{\n  /* multi\n  line\n  comment */\n  "key": "value"\n}'
        result = strip_jsonc_comments(text)
        assert json.loads(result) == {"key": "value"}

    def test_comment_chars_in_string_preserved(self):
        text = '{"url": "https://example.com"}'
        result = strip_jsonc_comments(text)
        assert json.loads(result) == {"url": "https://example.com"}

    def test_double_slash_in_string_preserved(self):
        text = '{"path": "a//b"}'
        result = strip_jsonc_comments(text)
        assert json.loads(result) == {"path": "a//b"}

    def test_no_comments(self):
        text = '{"key": "value"}'
        assert strip_jsonc_comments(text) == text


class TestResolveConfigPath:
    def test_explicit_override(self, tmp_path):
        config = tmp_path / "test.jsonc"
        config.write_text("{}")
        assert resolve_config_path(str(config)) == config

    def test_override_missing(self, tmp_path):
        assert resolve_config_path(str(tmp_path / "nonexistent.jsonc")) is None

    def test_none_override_searches_defaults(self):
        # With no override and potentially no config, returns None or a valid path
        result = resolve_config_path(None)
        assert result is None or result.is_file()


class TestFindTarget:
    def test_exact_match(self):
        config = {"personal": {"name": "Test"}}
        result = find_target(config, "personal")
        assert result == ("personal", {"name": "Test"})

    def test_case_insensitive(self):
        config = {"Personal": {"name": "Test"}}
        result = find_target(config, "personal")
        assert result is not None
        assert result[0] == "Personal"

    def test_not_found(self):
        config = {"personal": {"name": "Test"}}
        assert find_target(config, "nonexistent") is None


class TestResolveSshCommand:
    def test_default_key_returns_none(self):
        assert resolve_ssh_command("~/.ssh/id_ed25519.pub") is None

    def test_non_default_key(self):
        result = resolve_ssh_command("~/.ssh/id_ed25519_work.pub")
        assert result is not None
        assert "IdentitiesOnly=yes" in result
        assert "id_ed25519_work" in result

    def test_strips_pub_extension(self):
        result = resolve_ssh_command("~/Keys/custom_key.pub")
        assert result is not None
        assert ".pub" not in result


class TestSerializeConfig:
    def test_round_trip(self):
        data = {"key": "value", "nested": {"a": 1}}
        text = serialize_config(data)
        assert json.loads(text) == data

    def test_ends_with_newline(self):
        assert serialize_config({}).endswith("\n")

    def test_pretty_printed(self):
        text = serialize_config({"key": "value"})
        assert "\n" in text  # indented
