"""
Configuration management for the Novel Read server.
"""

import os
from pathlib import Path
from typing import Optional, List, Any
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import yaml


def _expand_env(value: Any) -> Any:
    """
    Recursively expand ``${VAR}`` / ``$VAR`` references in a value loaded from
    YAML. If a referenced variable is not set in the environment, the value is
    replaced with ``None`` so downstream code can detect "no key configured"
    instead of receiving the literal ``${VAR}`` string.
    """
    if isinstance(value, str):
        expanded = os.path.expandvars(value)
        # If nothing changed but the string still contains an unresolved
        # ${...} placeholder, the env var was not set -> treat as None.
        if expanded == value and "${" in value:
            return None
        return expanded
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


class AISettings(BaseSettings):
    """AI model settings."""
    endpoint: str = "https://api.openai.com/v1"
    model: str = "gpt-4"
    api_key: Optional[str] = None


class ChannelSettings(BaseSettings):
    """Channel configuration."""
    enabled: bool = True
    update_interval_hours: int = 6


class SearchEngineSettings(BaseSettings):
    """Search engine settings."""
    enabled: bool = True
    engines: List[str] = ["baidu", "bing", "so360"]


class P2PSettings(BaseSettings):
    """P2P distribution settings."""
    enabled: bool = True
    torrent_port: int = 6881
    download_dir: str = "./data/scripts"
    public_key_file: str = "./keys/public.pem"
    private_key_file: str = "./keys/private.pem"


# Map YAML keys under `server:` to Settings field names. YAML uses the short
# aliases (host/port/database) while the pydantic fields are named
# server_host/server_port/database_url.
_SERVER_KEY_MAP = {
    "host": "server_host",
    "port": "server_port",
    "database": "database_url",
    "debug": "debug",
    "api_key": "api_key",
    "jwt_secret": "jwt_secret",
    "jwt_expire_hours": "jwt_expire_hours",
    "log_level": "log_level",
    "log_file": "log_file",
}


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server settings
    server_host: str = Field(default="0.0.0.0", alias="host")
    server_port: int = Field(default=8080, alias="port")
    database_url: str = Field(default="sqlite+aiosqlite:///./data/novels.db", alias="database")
    debug: bool = False

    # Security
    api_key: str = "your-secret-api-key"
    jwt_secret: str = "your-jwt-secret-key"
    jwt_expire_hours: int = 24

    # AI settings
    ai_code_model: AISettings = Field(default_factory=AISettings)
    ai_vision_model: AISettings = Field(default_factory=AISettings)

    # Channels
    official_channel: ChannelSettings = Field(default_factory=ChannelSettings)
    search_channel: SearchEngineSettings = Field(default_factory=SearchEngineSettings)

    # P2P
    p2p: P2PSettings = Field(default_factory=P2PSettings)

    # Logging
    log_level: str = "INFO"
    log_file: str = "./logs/server.log"

    # Config file path
    config_file: str = "./config/server.yaml"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_config_file()

    def _load_config_file(self):
        """Load configuration from YAML file.

        Environment variables of the form ``${VAR}`` inside the YAML are
        expanded. Unresolved placeholders (variable not set) become ``None``.
        """
        config_path = Path(self.config_file)
        if not config_path.exists():
            return

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}")
            return

        if not config:
            return

        config = _expand_env(config)

        # --- server -----------------------------------------------------
        server_cfg = config.get("server") or {}
        for yaml_key, value in server_cfg.items():
            field_name = _SERVER_KEY_MAP.get(yaml_key)
            if field_name is None:
                continue
            if field_name == "database_url" and isinstance(value, str):
                # Allow YAML to specify either a bare path or a full
                # SQLAlchemy URL.
                if "://" not in value:
                    value = f"sqlite+aiosqlite:///{value}"
            if hasattr(self, field_name):
                setattr(self, field_name, value)

        # --- ai ---------------------------------------------------------
        ai_cfg = config.get("ai") or {}
        if "code_model" in ai_cfg and isinstance(ai_cfg["code_model"], dict):
            self.ai_code_model = AISettings(**ai_cfg["code_model"])
        if "vision_model" in ai_cfg and isinstance(ai_cfg["vision_model"], dict):
            self.ai_vision_model = AISettings(**ai_cfg["vision_model"])

        # --- channels ---------------------------------------------------
        channels_cfg = config.get("channels") or {}
        official_cfg = channels_cfg.get("official") or {}
        for key, value in official_cfg.items():
            if hasattr(self.official_channel, key):
                setattr(self.official_channel, key, value)

        search_cfg = channels_cfg.get("search") or {}
        for key, value in search_cfg.items():
            if hasattr(self.search_channel, key):
                setattr(self.search_channel, key, value)

        # --- p2p --------------------------------------------------------
        p2p_cfg = config.get("p2p") or {}
        for key, value in p2p_cfg.items():
            if hasattr(self.p2p, key):
                setattr(self.p2p, key, value)

        # --- logging ----------------------------------------------------
        log_cfg = config.get("logging") or {}
        if "level" in log_cfg:
            self.log_level = log_cfg["level"]
        if "file" in log_cfg:
            self.log_file = log_cfg["file"]


# Global settings instance
settings = Settings()
