"""Config + .env loading."""
from __future__ import annotations
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    raw: dict[str, Any] = field(default_factory=dict)
    root: Path = ROOT

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Config":
        load_dotenv(ROOT / ".env")
        path = Path(config_path) if config_path else ROOT / "config.yaml"
        if not path.exists():
            raise FileNotFoundError(f"config not found: {path}")
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        return cls(raw=raw)

    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    @staticmethod
    def env(key: str, default: str | None = None) -> str | None:
        return os.getenv(key, default)

    @property
    def cache_dir(self) -> Path:
        d = self.root / "cache"
        d.mkdir(exist_ok=True)
        return d

    @property
    def output_dir(self) -> Path:
        d = self.root / "output"
        d.mkdir(exist_ok=True)
        return d
