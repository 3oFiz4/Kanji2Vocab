# file: kanji2vocab/config.py
import json
from typing import Any

from .models import AppConfig
from .services.logger import Logger


class ConfigManager:
    """Handles reading and writing the config.json file."""
    def __init__(self, path: str, logger: Logger | None = None) -> None:
        # Store the config file path.
        self.path = path
        # Store logger for error reporting.
        self.logger = logger

    def load_raw(self) -> dict[str, Any]:
        """Load raw JSON as a dict."""
        # Open the config file and parse JSON.
        with open(self.path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_raw(self, data: dict[str, Any]) -> None:
        """Save raw JSON dict to disk."""
        # Write the JSON data with pretty formatting.
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def load(self) -> AppConfig:
        """Load AppConfig from JSON."""
        # Load raw JSON content.
        raw = self.load_raw()
        # Convert to AppConfig dataclass.
        return AppConfig.from_dict(raw)

    def save(self, config: AppConfig) -> None:
        """Save AppConfig to JSON."""
        # Convert config to dict and persist.
        self.save_raw(config.to_dict())

    def update_learned(self, config: AppConfig, kanji: str) -> AppConfig:
        """Add a kanji to has_learned if missing and persist."""
        # Check if the kanji is already recorded.
        if kanji not in config.has_learned:
            # Append new kanji to the list.
            config.has_learned.append(kanji)
            # Save updated config to disk.
            self.save(config)
            # Log the update if logger exists.
            if self.logger:
                self.logger.log(f"Added '{kanji}' to hasLearned.", "i")
        # Return (possibly) updated config.
        return config