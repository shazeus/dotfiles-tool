"""Configuration and state management for dotman."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

DOTMAN_HOME = Path(os.environ.get("DOTMAN_HOME", Path.home() / ".config" / "dotman"))
CONFIG_FILE = DOTMAN_HOME / "config.json"
STATE_FILE = DOTMAN_HOME / "state.json"


def ensure_dirs() -> None:
    DOTMAN_HOME.mkdir(parents=True, exist_ok=True)
    (DOTMAN_HOME / "profiles").mkdir(exist_ok=True)
    (DOTMAN_HOME / "backups").mkdir(exist_ok=True)


def load_config() -> Dict[str, Any]:
    ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {
        "dotfiles_dir": str(Path.home() / ".dotfiles"),
        "git_remote": "",
        "profiles": {},
        "active_profile": "default",
        "encrypt_secrets": False,
    }


def save_config(cfg: Dict[str, Any]) -> None:
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def load_state() -> Dict[str, Any]:
    ensure_dirs()
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"tracked": {}, "symlinks": {}}


def save_state(state: Dict[str, Any]) -> None:
    ensure_dirs()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_dotfiles_dir(cfg: Optional[Dict[str, Any]] = None) -> Path:
    if cfg is None:
        cfg = load_config()
    return Path(cfg["dotfiles_dir"])
