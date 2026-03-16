"""Tests for warden.cn module."""

from warden.cn import apply_cn_rewrites, detect_use_cn


class TestDetectUseCn:
    def test_not_set(self, monkeypatch):
        monkeypatch.delenv("WARDEN_USE_CN", raising=False)
        assert detect_use_cn() is False

    def test_set_1(self, monkeypatch):
        monkeypatch.setenv("WARDEN_USE_CN", "1")
        assert detect_use_cn() is True

    def test_set_true(self, monkeypatch):
        monkeypatch.setenv("WARDEN_USE_CN", "true")
        assert detect_use_cn() is True

    def test_set_yes(self, monkeypatch):
        monkeypatch.setenv("WARDEN_USE_CN", "yes")
        assert detect_use_cn() is True

    def test_set_TRUE(self, monkeypatch):
        monkeypatch.setenv("WARDEN_USE_CN", "TRUE")
        assert detect_use_cn() is True

    def test_set_0(self, monkeypatch):
        monkeypatch.setenv("WARDEN_USE_CN", "0")
        assert detect_use_cn() is False

    def test_set_empty(self, monkeypatch):
        monkeypatch.setenv("WARDEN_USE_CN", "")
        assert detect_use_cn() is False


class TestApplyCnRewrites:
    def test_rustup_rewrite(self):
        cmd = 'curl --proto "=https" --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y'
        result = apply_cn_rewrites(cmd)
        assert "rsproxy.cn" in result
        assert "sh.rustup.rs" not in result

    def test_github_rewrite(self):
        cmd = "git clone https://github.com/flutter/flutter.git"
        result = apply_cn_rewrites(cmd)
        assert "ghp.ci" in result
        assert result == "git clone https://ghp.ci/https://github.com/flutter/flutter.git"

    def test_fnm_rewrite(self):
        cmd = "curl -fsSL https://fnm.vercel.app/install | bash"
        result = apply_cn_rewrites(cmd)
        assert "ghp.ci" in result

    def test_pnpm_rewrite(self):
        cmd = "curl -fsSL https://get.pnpm.io/install.sh | sh -"
        result = apply_cn_rewrites(cmd)
        assert "ghp.ci" in result

    def test_no_rewrite_needed(self):
        cmd = "apt-get install -y curl"
        assert apply_cn_rewrites(cmd) == cmd
