"""
Configuration management for the Novel Read server.
"""

import os
from pathlib import Path
from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import Field
import yaml


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


class Settings(BaseSettings):
    """Application settings."""
    
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
    
    class Config:
        env_file = ".env"
        extra = "ignore"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_config_file()
    
    def _load_config_file(self):
        """Load configuration from YAML file."""
        config_path = Path(self.config_file)
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                
                if config:
                    # Update settings from config
                    if 'server' in config:
                        for key, value in config['server'].items():
                            if hasattr(self, key):
                                setattr(self, key, value)
                    
                    if 'ai' in config:
                        if 'code_model' in config['ai']:
                            self.ai_code_model = AISettings(**config['ai']['code_model'])
                        if 'vision_model' in config['ai']:
                            self.ai_vision_model = AISettings(**config['ai']['vision_model'])
                            
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")


# Global settings instance
settings = Settings()
