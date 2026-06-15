"""Config loading + path helpers shared across the package."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

# Project root = parent of this package directory.
ROOT = Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """Load config.yaml from the project root."""
    cfg_path = ROOT / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def db_path(cfg: dict) -> Path:
    p = Path(cfg.get("db_path", "data/finance.db"))
    return p if p.is_absolute() else ROOT / p


def digests_dir(cfg: dict) -> Path:
    p = Path(cfg.get("digests_dir", "data/digests"))
    return p if p.is_absolute() else ROOT / p


def anthropic_key() -> str | None:
    return os.environ.get("ANTHROPIC_API_KEY") or None
