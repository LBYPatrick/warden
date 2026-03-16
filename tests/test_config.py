"""Tests for warden.config module."""

import json5

from warden.config import (
    find_target,
    get_identities,
    get_packages,
    get_tools,
    is_new_format,
    merge_configs,
    resolve_config_path,
    resolve_ssh_command,
    serialize_config,
    update_packages,
)


class TestJson5Parsing:
    """Test that json5 handles JSONC features we rely on."""

    def test_line_comments(self):
        text = '{\n  // comment\n  "key": "value"\n}'
        assert json5.loads(text) == {"key": "value"}

    def test_block_comments(self):
        text = '{\n  /* block */\n  "key": "value"\n}'
        assert json5.loads(text) == {"key": "value"}

    def test_trailing_commas(self):
        text = '{"a": 1, "b": 2,}'
        assert json5.loads(text) == {"a": 1, "b": 2}

    def test_comment_chars_in_string_preserved(self):
        text = '{"url": "https://example.com"}'
        assert json5.loads(text) == {"url": "https://example.com"}

    def test_double_slash_in_string_preserved(self):
        text = '{"path": "a//b"}'
        assert json5.loads(text) == {"path": "a//b"}


class TestResolveConfigPath:
    def test_explicit_override(self, tmp_path):
        config = tmp_path / "test.jsonc"
        config.write_text("{}")
        assert resolve_config_path(str(config)) == config

    def test_override_missing(self, tmp_path):
        assert resolve_config_path(str(tmp_path / "nonexistent.jsonc")) is None

    def test_none_override_searches_defaults(self):
        result = resolve_config_path(None)
        assert result is None or result.is_file()


class TestFormatDetection:
    def test_new_format(self):
        config = {"identities": {"personal": {}}, "packages": {}, "tools": []}
        assert is_new_format(config) is True

    def test_legacy_format(self):
        config = {"personal": {"name": "Test"}}
        assert is_new_format(config) is False


class TestGetIdentities:
    def test_new_format(self):
        config = {"identities": {"personal": {"name": "Test"}}, "packages": {}}
        assert get_identities(config) == {"personal": {"name": "Test"}}

    def test_legacy_format(self):
        config = {"personal": {"name": "Test"}, "work": {"name": "Work"}}
        ids = get_identities(config)
        assert "personal" in ids
        assert "work" in ids

    def test_empty_config(self):
        assert get_identities({}) == {}


class TestGetPackages:
    def test_with_packages(self):
        config = {"packages": {"brew": {"formulae": ["git"]}}}
        assert get_packages(config) == {"brew": {"formulae": ["git"]}}

    def test_without_packages(self):
        assert get_packages({"identities": {}}) == {}


class TestGetTools:
    def test_with_tools(self):
        config = {"tools": ["rustup", "node"]}
        assert get_tools(config) == ["rustup", "node"]

    def test_without_tools(self):
        assert get_tools({}) == []


class TestFindTarget:
    def test_exact_match(self):
        identities = {"personal": {"name": "Test"}}
        result = find_target(identities, "personal")
        assert result == ("personal", {"name": "Test"})

    def test_case_insensitive(self):
        identities = {"Personal": {"name": "Test"}}
        result = find_target(identities, "personal")
        assert result is not None
        assert result[0] == "Personal"

    def test_not_found(self):
        identities = {"personal": {"name": "Test"}}
        assert find_target(identities, "nonexistent") is None


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
        assert json5.loads(text) == data

    def test_ends_with_newline(self):
        assert serialize_config({}).endswith("\n")

    def test_pretty_printed(self):
        text = serialize_config({"key": "value"})
        assert "\n" in text


class TestMergeConfigs:
    def test_merge_identities(self):
        existing = {
            "identities": {"personal": {"name": "Old"}},
        }
        incoming = {
            "identities": {"personal": {"name": "New"}, "work": {"name": "Work"}},
        }
        merged = merge_configs(existing, incoming)
        assert merged["identities"]["personal"]["name"] == "New"
        assert merged["identities"]["work"]["name"] == "Work"

    def test_merge_preserves_existing_packages(self):
        existing = {
            "identities": {"personal": {"name": "Test"}},
            "packages": {"brew": {"formulae": ["git", "curl"]}},
        }
        incoming = {
            "identities": {"personal": {"name": "Test"}},
        }
        merged = merge_configs(existing, incoming)
        assert "git" in merged["packages"]["brew"]["formulae"]
        assert "curl" in merged["packages"]["brew"]["formulae"]

    def test_merge_packages_union(self):
        existing = {
            "packages": {"brew": {"formulae": ["git", "curl"], "casks": ["firefox"]}},
        }
        incoming = {
            "packages": {"brew": {"formulae": ["git", "ripgrep"], "casks": ["chrome"]}},
        }
        merged = merge_configs(existing, incoming)
        formulae = merged["packages"]["brew"]["formulae"]
        casks = merged["packages"]["brew"]["casks"]
        assert set(formulae) == {"git", "curl", "ripgrep"}
        assert set(casks) == {"firefox", "chrome"}
        # Sorted
        assert formulae == sorted(formulae)
        assert casks == sorted(casks)

    def test_merge_tools_union(self):
        existing = {"tools": ["rustup", "node"]}
        incoming = {"tools": ["node", "pnpm"]}
        merged = merge_configs(existing, incoming)
        assert set(merged["tools"]) == {"rustup", "node", "pnpm"}
        assert merged["tools"] == sorted(merged["tools"])

    def test_merge_apt_packages(self):
        existing = {"packages": {"apt": {"packages": ["curl", "git"]}}}
        incoming = {"packages": {"apt": {"packages": ["git", "wget"]}}}
        merged = merge_configs(existing, incoming)
        pkgs = merged["packages"]["apt"]["packages"]
        assert set(pkgs) == {"curl", "git", "wget"}

    def test_merge_empty_existing(self):
        incoming = {
            "identities": {"work": {"name": "Work"}},
            "tools": ["node"],
        }
        merged = merge_configs({}, incoming)
        assert merged["identities"]["work"]["name"] == "Work"
        assert merged["tools"] == ["node"]

    def test_merge_empty_incoming(self):
        existing = {
            "identities": {"personal": {"name": "Test"}},
            "packages": {"brew": {"formulae": ["git"]}},
        }
        merged = merge_configs(existing, {})
        assert merged["identities"]["personal"]["name"] == "Test"
        assert "git" in merged["packages"]["brew"]["formulae"]

    def test_merge_legacy_with_new(self):
        existing = {"personal": {"name": "Old"}}  # legacy
        incoming = {
            "identities": {"personal": {"name": "New"}, "work": {"name": "Work"}},
            "tools": ["node"],
        }
        merged = merge_configs(existing, incoming)
        assert merged["identities"]["personal"]["name"] == "New"
        assert merged["identities"]["work"]["name"] == "Work"
        assert merged["tools"] == ["node"]


class TestUpdatePackages:
    def test_replaces_packages(self):
        config = {
            "identities": {"personal": {"name": "Test"}},
            "packages": {"brew": {"formulae": ["old"]}},
            "tools": ["old-tool"],
        }
        result = update_packages(
            config,
            {"brew": {"formulae": ["new1", "new2"]}},
            ["new-tool"],
        )
        assert result["identities"]["personal"]["name"] == "Test"
        assert result["packages"]["brew"]["formulae"] == ["new1", "new2"]
        assert result["tools"] == ["new-tool"]

    def test_preserves_identities_from_legacy(self):
        config = {"personal": {"name": "Test"}}
        result = update_packages(config, {}, ["node"])
        assert result["identities"]["personal"]["name"] == "Test"
        assert result["tools"] == ["node"]
