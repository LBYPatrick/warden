"""Tests for warden.ssh_config module."""

from pathlib import Path

from warden.ssh_config import (
    get_identity_files,
    merge_ssh_configs,
    parse_ssh_config,
    rewrite_identity_files,
    serialize_ssh_config,
)

SAMPLE_CONFIG = """\
# Global options
Host test-server
  HostName 192.168.1.1
  User testuser
  IdentityFile ~/.ssh/id_test

Host prod-server
  HostName 10.0.0.1
  User admin
  Port 2222
"""


class TestParseSshConfig:
    def test_preamble_extracted(self):
        preamble, blocks = parse_ssh_config(SAMPLE_CONFIG)
        assert any("Global" in line for line in preamble)

    def test_blocks_extracted(self):
        _, blocks = parse_ssh_config(SAMPLE_CONFIG)
        assert len(blocks) == 2
        assert blocks[0].name == "Host test-server"
        assert blocks[1].name == "Host prod-server"

    def test_options_parsed(self):
        _, blocks = parse_ssh_config(SAMPLE_CONFIG)
        assert blocks[0].options["HostName"] == "192.168.1.1"
        assert blocks[0].options["User"] == "testuser"
        assert blocks[0].options["IdentityFile"] == "~/.ssh/id_test"
        assert blocks[1].options["Port"] == "2222"

    def test_lines_preserved(self):
        _, blocks = parse_ssh_config(SAMPLE_CONFIG)
        assert any("HostName" in line for line in blocks[0].lines)

    def test_empty_config(self):
        preamble, blocks = parse_ssh_config("")
        assert preamble == []
        assert blocks == []


class TestSerializeSshConfig:
    def test_round_trip(self):
        preamble, blocks = parse_ssh_config(SAMPLE_CONFIG)
        result = serialize_ssh_config(preamble, blocks)
        # Parse again and check structure matches
        p2, b2 = parse_ssh_config(result)
        assert len(b2) == len(blocks)
        for orig, roundtripped in zip(blocks, b2):
            assert orig.name == roundtripped.name
            assert orig.options == roundtripped.options

    def test_ends_with_newline(self):
        preamble, blocks = parse_ssh_config(SAMPLE_CONFIG)
        result = serialize_ssh_config(preamble, blocks)
        assert result.endswith("\n")


class TestMergeSshConfigs:
    def test_update_existing(self):
        existing = "Host foo\n  HostName old.example.com\n  User old\n"
        restored = "Host foo\n  HostName new.example.com\n  User new\n"
        merged, updated, added = merge_ssh_configs(existing, restored)
        assert updated == 1
        assert added == 0
        assert "new.example.com" in merged
        assert "old.example.com" not in merged

    def test_append_new(self):
        existing = "Host foo\n  HostName foo.com\n"
        restored = "Host bar\n  HostName bar.com\n"
        merged, updated, added = merge_ssh_configs(existing, restored)
        assert updated == 0
        assert added == 1
        assert "foo.com" in merged
        assert "bar.com" in merged

    def test_mixed_update_and_add(self):
        existing = "Host foo\n  HostName old.com\n"
        restored = "Host foo\n  HostName new.com\nHost bar\n  HostName bar.com\n"
        merged, updated, added = merge_ssh_configs(existing, restored)
        assert updated == 1
        assert added == 1

    def test_empty_existing(self):
        restored = "Host foo\n  HostName foo.com\n"
        merged, updated, added = merge_ssh_configs("", restored)
        assert added == 1
        assert "foo.com" in merged


class TestGetIdentityFiles:
    def test_extracts_identity_files(self):
        _, blocks = parse_ssh_config(SAMPLE_CONFIG)
        result = get_identity_files(blocks)
        assert "Host test-server" in result
        assert "Host prod-server" not in result

    def test_empty_blocks(self):
        assert get_identity_files([]) == {}


class TestRewriteIdentityFiles:
    def test_rewrites_matching_paths(self):
        _, blocks = parse_ssh_config(SAMPLE_CONFIG)
        # Resolve the path to match what the code does
        original = str(Path("~/.ssh/id_test").expanduser().resolve())
        path_map = {original: "~/.warden/keys/id_test_abc123"}
        result = rewrite_identity_files(blocks, path_map)
        found = False
        for block in result:
            if block.name == "Host test-server":
                assert block.options["IdentityFile"] == "~/.warden/keys/id_test_abc123"
                found = True
        assert found

    def test_skips_unmatched(self):
        _, blocks = parse_ssh_config(SAMPLE_CONFIG)
        result = rewrite_identity_files(blocks, {})
        # prod-server has no IdentityFile, should pass through
        assert len(result) == len(blocks)
