"""Loads config.yaml, merges the active environment's overrides, then applies .env/OS env overrides."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


class ConfigReader:
    """Singleton-style reader exposing merged configuration via ConfigReader.get(key)."""

    _CONFIG_DIR = Path(__file__).parent
    _config_cache = None

    @classmethod
    def get_config(cls) -> dict:
        if cls._config_cache is not None:
            return cls._config_cache

        base_config_path = cls._CONFIG_DIR / "config.yaml"
        with open(base_config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}

        env = os.getenv("ENV", config.get("environment", "qa")).lower()
        env_config_path = cls._CONFIG_DIR / "environments" / f"{env}.yaml"
        if env_config_path.exists():
            with open(env_config_path, "r", encoding="utf-8") as f:
                config.update(yaml.safe_load(f) or {})

        # OS/`.env` variables take the highest precedence, useful for CI overrides
        if os.getenv("BASE_URL"):
            config["base_url"] = os.getenv("BASE_URL")
        if os.getenv("API_BASE_URL"):
            config["api_base_url"] = os.getenv("API_BASE_URL")
        if os.getenv("BROWSER"):
            config["browser"] = os.getenv("BROWSER")
        if os.getenv("HEADLESS"):
            config["headless"] = os.getenv("HEADLESS").strip().lower() == "true"
        if os.getenv("DB_CONNECTION_STRING"):
            config["db_connection_string"] = os.getenv("DB_CONNECTION_STRING")
        if os.getenv("AI_ENABLED"):
            config["ai_enabled"] = os.getenv("AI_ENABLED").strip().lower() == "true"
        if os.getenv("OLLAMA_HOST"):
            config["ollama_host"] = os.getenv("OLLAMA_HOST")
        if os.getenv("OLLAMA_MODEL"):
            config["ollama_model"] = os.getenv("OLLAMA_MODEL")

        config["environment"] = env
        cls._config_cache = config
        return config

    @classmethod
    def get(cls, key: str, default=None):
        return cls.get_config().get(key, default)
