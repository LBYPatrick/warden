"""Shared fixtures for warden tests. No real keys or sensitive data."""

import pytest


@pytest.fixture()
def fake_keys(tmp_path):
    """Create fake key files in a temp directory."""
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()

    # Default key pair
    priv = ssh_dir / "id_ed25519"
    priv.write_text("FAKE-PRIVATE-KEY-DEFAULT")
    priv.chmod(0o600)
    pub = ssh_dir / "id_ed25519.pub"
    pub.write_text("ssh-ed25519 AAAA fake@test")

    # Non-default key pair
    priv2 = ssh_dir / "id_ed25519_work"
    priv2.write_text("FAKE-PRIVATE-KEY-WORK")
    priv2.chmod(0o600)
    pub2 = ssh_dir / "id_ed25519_work.pub"
    pub2.write_text("ssh-ed25519 BBBB work@test")

    return ssh_dir


@pytest.fixture()
def fake_warden_config(tmp_path, fake_keys):
    """Create a fake warden.jsonc config file in the new format."""
    config_path = tmp_path / ".ssh" / "warden.jsonc"
    ssh_dir = fake_keys
    config_path.write_text(
        f"{{\n"
        f"  // Test config\n"
        f'  "identities": {{\n'
        f'    "personal": {{\n'
        f'      "name": "Test User",\n'
        f'      "email": "test@example.com",\n'
        f'      "signing_key": "{ssh_dir / "id_ed25519.pub"}"\n'
        f"    }},\n"
        f'    "work": {{\n'
        f'      "name": "Work User",\n'
        f'      "email": "work@example.com",\n'
        f'      "signing_key": "{ssh_dir / "id_ed25519_work.pub"}"\n'
        f"    }}\n"
        f"  }},\n"
        f'  "packages": {{\n'
        f'    "brew": {{\n'
        f'      "formulae": ["git", "ripgrep"],\n'
        f'      "casks": ["firefox"]\n'
        f"    }}\n"
        f"  }},\n"
        f'  "tools": ["rustup", "node"]\n'
        f"}}"
    )
    return config_path


@pytest.fixture()
def fake_legacy_config(tmp_path, fake_keys):
    """Create a fake warden.jsonc config file in the legacy format."""
    config_path = tmp_path / ".ssh" / "warden.jsonc"
    ssh_dir = fake_keys
    config_path.write_text(
        f"{{\n"
        f"  // Legacy config\n"
        f'  "personal": {{\n'
        f'    "name": "Test User",\n'
        f'    "email": "test@example.com",\n'
        f'    "signing_key": "{ssh_dir / "id_ed25519.pub"}"\n'
        f"  }},\n"
        f'  "work": {{\n'
        f'    "name": "Work User",\n'
        f'    "email": "work@example.com",\n'
        f'    "signing_key": "{ssh_dir / "id_ed25519_work.pub"}"\n'
        f"  }}\n"
        f"}}"
    )
    return config_path


@pytest.fixture()
def fake_ssh_config(tmp_path, fake_keys):
    """Create a fake SSH config file."""
    ssh_dir = fake_keys
    config_path = tmp_path / ".ssh" / "config"
    config_path.write_text(
        f"# Test SSH config\n"
        f"Host test-server\n"
        f"  HostName 192.168.1.1\n"
        f"  User testuser\n"
        f"  IdentityFile {ssh_dir / 'id_ed25519_work'}\n"
        f"\n"
        f"Host default-server\n"
        f"  HostName 10.0.0.1\n"
        f"  User admin\n"
        f"  IdentityFile {ssh_dir / 'id_ed25519'}\n"
    )
    return config_path
