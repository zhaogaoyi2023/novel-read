"""
Tests for the configuration loader (server.core.config).

Verifies:
- YAML alias keys (host/port/database) map to the correct Settings fields.
- Bare database paths are upgraded to full SQLAlchemy URLs.
- ${VAR} env references are expanded; unset vars become None.
- Sections other than server/ai (channels, p2p, logging) are applied.
"""

import os
from pathlib import Path

import pytest


def test_default_settings():
    from server.core.config import AISettings, Settings
    s = Settings(config_file="/nonexistent/path.yaml")
    assert s.server_host == "0.0.0.0"
    assert s.server_port == 8080
    assert s.database_url.startswith("sqlite+aiosqlite:///")
    assert s.ai_code_model.api_key is None


def test_yaml_alias_keys_mapped(tmp_path, monkeypatch):
    cfg = tmp_path / "server.yaml"
    cfg.write_text(
        """
server:
  host: "127.0.0.1"
  port: 9999
  database: "/tmp/test_novels.db"
  debug: true
  api_key: "key-from-yaml"
  jwt_secret: "secret-from-yaml"
  jwt_expire_hours: 12
""",
        encoding="utf-8",
    )
    from server.core.config import Settings
    s = Settings(config_file=str(cfg))
    assert s.server_host == "127.0.0.1"
    assert s.server_port == 9999
    assert s.database_url == "sqlite+aiosqlite:////tmp/test_novels.db"
    assert s.debug is True
    assert s.api_key == "key-from-yaml"
    assert s.jwt_secret == "secret-from-yaml"
    assert s.jwt_expire_hours == 12


def test_database_url_pass_through(tmp_path):
    cfg = tmp_path / "server.yaml"
    cfg.write_text(
        """
server:
  database: "postgresql+asyncpg://user:pass@host/db"
""",
        encoding="utf-8",
    )
    from server.core.config import Settings
    s = Settings(config_file=str(cfg))
    assert s.database_url == "postgresql+asyncpg://user:pass@host/db"


def test_env_var_expansion_when_set(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-real-key")
    cfg = tmp_path / "server.yaml"
    cfg.write_text(
        """
ai:
  code_model:
    endpoint: "https://api.openai.com/v1"
    model: "gpt-4"
    api_key: "${OPENAI_API_KEY}"
""",
        encoding="utf-8",
    )
    from server.core.config import Settings
    s = Settings(config_file=str(cfg))
    assert s.ai_code_model.api_key == "sk-real-key"


def test_env_var_unset_becomes_none(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    cfg = tmp_path / "server.yaml"
    cfg.write_text(
        """
ai:
  code_model:
    api_key: "${OPENAI_API_KEY}"
""",
        encoding="utf-8",
    )
    from server.core.config import Settings
    s = Settings(config_file=str(cfg))
    assert s.ai_code_model.api_key is None


def test_channels_and_p2p_and_logging_loaded(tmp_path):
    cfg = tmp_path / "server.yaml"
    cfg.write_text(
        """
channels:
  official:
    enabled: false
    update_interval_hours: 24
  search:
    enabled: false
    engines:
      - baidu
p2p:
  enabled: false
  torrent_port: 12345
logging:
  level: "DEBUG"
  file: "./logs/custom.log"
""",
        encoding="utf-8",
    )
    from server.core.config import Settings
    s = Settings(config_file=str(cfg))
    assert s.official_channel.enabled is False
    assert s.official_channel.update_interval_hours == 24
    assert s.search_channel.enabled is False
    assert s.search_channel.engines == ["baidu"]
    assert s.p2p.enabled is False
    assert s.p2p.torrent_port == 12345
    assert s.log_level == "DEBUG"
    assert s.log_file == "./logs/custom.log"
