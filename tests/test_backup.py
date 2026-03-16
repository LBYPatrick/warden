"""Tests for warden.backup module."""

import json
import tarfile

from warden.backup import (
    MARKER_FILE,
    _add_bytes_to_tar,
    _collect_key_files,
    _strip_existing_hash,
    _validate_archive,
    _validate_tar_member,
    _write_marker,
    backup_all,
    backup_git,
    backup_ssh,
    hashed_key_name,
    path_hash,
    restore_all,
    restore_git,
    restore_ssh,
)


class TestPathHash:
    def test_deterministic(self):
        assert path_hash("/some/path") == path_hash("/some/path")

    def test_six_chars(self):
        assert len(path_hash("/some/path")) == 6

    def test_hex_chars(self):
        h = path_hash("/test")
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_paths_differ(self):
        assert path_hash("/a") != path_hash("/b")


class TestStripExistingHash:
    def test_strips_hash(self):
        assert _strip_existing_hash("id_ed25519_abc123") == "id_ed25519"

    def test_no_hash_unchanged(self):
        assert _strip_existing_hash("id_ed25519") == "id_ed25519"

    def test_preserves_non_hex_suffix(self):
        assert _strip_existing_hash("id_ed25519_work") == "id_ed25519_work"

    def test_only_strips_6_char_hex(self):
        # 5 chars is not a hash
        assert _strip_existing_hash("key_abcde") == "key_abcde"
        # 7 chars is not a hash
        assert _strip_existing_hash("key_abcdef0") == "key_abcdef0"


class TestHashedKeyName:
    def test_with_extension(self):
        assert hashed_key_name("id_ed25519.pub", "abc123") == "id_ed25519_abc123.pub"

    def test_without_extension(self):
        assert hashed_key_name("my_key", "abc123") == "my_key_abc123"

    def test_pem_extension(self):
        assert hashed_key_name("cert.pem", "abc123") == "cert_abc123.pem"

    def test_no_hash_stacking(self):
        # First hash
        name1 = hashed_key_name("id_ed25519.pub", "abc123")
        assert name1 == "id_ed25519_abc123.pub"
        # Second hash should replace, not stack
        name2 = hashed_key_name(name1, "def456")
        assert name2 == "id_ed25519_def456.pub"
        assert "abc123" not in name2

    def test_no_hash_stacking_no_ext(self):
        name1 = hashed_key_name("my_key", "abc123")
        name2 = hashed_key_name(name1, "def456")
        assert name2 == "my_key_def456"
        assert "abc123" not in name2


class TestCollectKeyFiles:
    def test_finds_private_and_pub(self, fake_keys):
        files = _collect_key_files(str(fake_keys / "id_ed25519.pub"))
        assert len(files) == 2
        names = {f.name for f, _ in files}
        assert "id_ed25519" in names
        assert "id_ed25519.pub" in names

    def test_finds_from_private_path(self, fake_keys):
        files = _collect_key_files(str(fake_keys / "id_ed25519"))
        assert len(files) == 2

    def test_missing_key_returns_empty(self, tmp_path):
        files = _collect_key_files(str(tmp_path / "nonexistent.pub"))
        assert files == []


class TestValidateTarMember:
    def test_normal_path(self):
        assert _validate_tar_member("keys/my_key") is True

    def test_rejects_absolute(self):
        assert _validate_tar_member("/etc/passwd") is False

    def test_rejects_traversal(self):
        assert _validate_tar_member("../../../etc/passwd") is False

    def test_nested_traversal(self):
        assert _validate_tar_member("keys/../../etc/passwd") is False


class TestMarkerFile:
    def test_write_and_validate(self, tmp_path):
        archive = tmp_path / "test.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            _write_marker(tar, "git")
            _add_bytes_to_tar(tar, "warden.jsonc", b"{}")

        with tarfile.open(str(archive), "r:gz") as tar:
            assert _validate_archive(tar, "git") is True

    def test_wrong_type_fails(self, tmp_path):
        archive = tmp_path / "test.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            _write_marker(tar, "git")
            _add_bytes_to_tar(tar, "warden.jsonc", b"{}")

        with tarfile.open(str(archive), "r:gz") as tar:
            assert _validate_archive(tar, "ssh") is False

    def test_missing_marker_fails(self, tmp_path):
        archive = tmp_path / "test.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            _add_bytes_to_tar(tar, "warden.jsonc", b"{}")

        with tarfile.open(str(archive), "r:gz") as tar:
            assert _validate_archive(tar, "git") is False

    def test_missing_content_file_fails(self, tmp_path):
        archive = tmp_path / "test.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            _write_marker(tar, "ssh")
            # Missing ssh_config file

        with tarfile.open(str(archive), "r:gz") as tar:
            assert _validate_archive(tar, "ssh") is False

    def test_all_type_needs_both(self, tmp_path):
        archive = tmp_path / "test.tar.gz"
        with tarfile.open(str(archive), "w:gz") as tar:
            _write_marker(tar, "all")
            _add_bytes_to_tar(tar, "warden.jsonc", b"{}")
            _add_bytes_to_tar(tar, "ssh_config", b"Host test\n  HostName test\n")

        with tarfile.open(str(archive), "r:gz") as tar:
            assert _validate_archive(tar, "all") is True


class TestBackupRestoreGitEndToEnd:
    def test_backup_and_restore(self, tmp_path, fake_keys, fake_warden_config):
        archive = tmp_path / "git-backup.tar.gz"
        config_data = json.loads(
            fake_warden_config.read_text().replace(
                "// Test config\n",
                "",  # strip comment for json.loads
            )
        )

        # Backup
        backup_git(fake_warden_config, config_data, str(archive))
        assert archive.is_file()

        # Verify archive contents
        with tarfile.open(str(archive), "r:gz") as tar:
            names = tar.getnames()
            assert MARKER_FILE in names
            assert "warden.jsonc" in names
            key_files = [n for n in names if n.startswith("keys/")]
            assert len(key_files) > 0

        # Restore to a new location
        restore_dir = tmp_path / "restore_home"
        restore_dir.mkdir()
        import warden.backup as bmod

        orig_warden = bmod.WARDEN_DIR
        orig_keys = bmod.KEYS_DIR
        try:
            bmod.WARDEN_DIR = restore_dir / ".warden"
            bmod.KEYS_DIR = bmod.WARDEN_DIR / "keys"
            restore_git(archive)
            assert (bmod.WARDEN_DIR / "warden.jsonc").is_file()
            assert bmod.KEYS_DIR.is_dir()
            restored_keys = list(bmod.KEYS_DIR.iterdir())
            assert len(restored_keys) > 0
        finally:
            bmod.WARDEN_DIR = orig_warden
            bmod.KEYS_DIR = orig_keys


class TestBackupRestoreSshEndToEnd:
    def test_backup_and_restore(
        self, tmp_path, fake_keys, fake_ssh_config, monkeypatch
    ):
        archive = tmp_path / "ssh-backup.tar.gz"

        # Point Path.home() to tmp_path so backup finds the fake ssh config
        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        import warden.backup as bmod

        orig_warden = bmod.WARDEN_DIR
        orig_keys = bmod.KEYS_DIR
        try:
            bmod.WARDEN_DIR = tmp_path / ".warden"
            bmod.KEYS_DIR = bmod.WARDEN_DIR / "keys"

            backup_ssh(str(archive))
            assert archive.is_file()

            with tarfile.open(str(archive), "r:gz") as tar:
                names = tar.getnames()
                assert MARKER_FILE in names
                assert "ssh_config" in names

            # Remove original config to test fresh restore
            (tmp_path / ".ssh" / "config").unlink()
            restore_ssh(archive)
            assert (tmp_path / ".ssh" / "config").is_file()
        finally:
            bmod.WARDEN_DIR = orig_warden
            bmod.KEYS_DIR = orig_keys


class TestBackupRestoreAllEndToEnd:
    def test_backup_and_restore(
        self, tmp_path, fake_keys, fake_warden_config, fake_ssh_config, monkeypatch
    ):
        archive = tmp_path / "all-backup.tar.gz"

        monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)

        config_data = json.loads(
            fake_warden_config.read_text().replace("// Test config\n", "")
        )

        import warden.backup as bmod

        orig_warden = bmod.WARDEN_DIR
        orig_keys = bmod.KEYS_DIR
        try:
            bmod.WARDEN_DIR = tmp_path / ".warden"
            bmod.KEYS_DIR = bmod.WARDEN_DIR / "keys"

            backup_all(fake_warden_config, config_data, str(archive))
            assert archive.is_file()

            with tarfile.open(str(archive), "r:gz") as tar:
                names = tar.getnames()
                assert MARKER_FILE in names
                assert "warden.jsonc" in names
                assert "ssh_config" in names

            # Restore
            (tmp_path / ".ssh" / "config").unlink()
            restore_all(archive)
            assert (bmod.WARDEN_DIR / "warden.jsonc").is_file()
            assert (tmp_path / ".ssh" / "config").is_file()
            assert bmod.KEYS_DIR.is_dir()
        finally:
            bmod.WARDEN_DIR = orig_warden
            bmod.KEYS_DIR = orig_keys
