"""Profile management for dotman."""

import json
import shutil
from pathlib import Path
from typing import List, Tuple

from dotman.config import (
    DOTMAN_HOME,
    get_dotfiles_dir,
    load_config,
    load_state,
    save_config,
    save_state,
)


def list_profiles() -> List[str]:
    cfg = load_config()
    dotfiles_dir = get_dotfiles_dir(cfg)
    state = load_state()
    profiles = {"default", *cfg.get("profiles", {}).keys()}

    if dotfiles_dir.exists():
        profiles.update(
            child.name
            for child in dotfiles_dir.iterdir()
            if child.is_dir() and not child.name.startswith(".") and child.name != "backups"
        )

    for entry in state.get("tracked", {}).values():
        profiles.add(entry.get("profile", "default"))

    return sorted(profiles)


def create_profile(name: str) -> Tuple[bool, str]:
    cfg = load_config()
    dotfiles_dir = get_dotfiles_dir(cfg)
    profile_dir = dotfiles_dir / name
    if profile_dir.exists():
        return False, f"Profile '{name}' already exists."
    profile_dir.mkdir(parents=True, exist_ok=True)
    cfg.setdefault("profiles", {})[name] = {}
    save_config(cfg)
    return True, f"Profile '{name}' created at {profile_dir}"


def delete_profile(name: str, force: bool = False) -> Tuple[bool, str]:
    if name == "default":
        return False, "Cannot delete the 'default' profile."
    state = load_state()
    tracked = state.get("tracked", {})
    profile_files = [k for k, v in tracked.items() if v.get("profile") == name]
    if profile_files and not force:
        return False, (
            f"Profile '{name}' has {len(profile_files)} tracked file(s). "
            "Use --force to delete anyway."
        )
    cfg = load_config()
    dotfiles_dir = get_dotfiles_dir(cfg)
    profile_dir = dotfiles_dir / name
    if profile_dir.exists():
        shutil.rmtree(str(profile_dir))
    for key in profile_files:
        del tracked[key]
    save_state(state)
    cfg = load_config()
    cfg.get("profiles", {}).pop(name, None)
    if cfg.get("active_profile") == name:
        cfg["active_profile"] = "default"
    save_config(cfg)
    return True, f"Profile '{name}' deleted."


def switch_profile(name: str) -> Tuple[bool, str]:
    if name not in list_profiles():
        return False, f"Profile '{name}' does not exist."
    cfg = load_config()
    cfg["active_profile"] = name
    save_config(cfg)
    return True, f"Active profile set to '{name}'."


def get_active_profile() -> str:
    cfg = load_config()
    return cfg.get("active_profile", "default")


def export_profile(name: str, output_path: Path) -> Tuple[bool, str]:
    """Export a profile's file list to a JSON manifest."""
    state = load_state()
    tracked = state.get("tracked", {})
    entries = {k: v for k, v in tracked.items() if v.get("profile") == name}
    if not entries:
        return False, f"No tracked files in profile '{name}'."
    manifest = {"profile": name, "files": entries}
    output_path.write_text(json.dumps(manifest, indent=2))
    return True, f"Exported {len(entries)} file(s) to {output_path}"


def import_profile(manifest_path: Path) -> Tuple[bool, str]:
    """Import a profile manifest (re-creates tracking entries; does not move files)."""
    if not manifest_path.exists():
        return False, f"Manifest not found: {manifest_path}"
    data = json.loads(manifest_path.read_text())
    state = load_state()
    tracked = state.setdefault("tracked", {})
    imported = 0
    for key, entry in data.get("files", {}).items():
        if key not in tracked:
            tracked[key] = entry
            imported += 1
    save_state(state)
    return True, f"Imported {imported} file(s) from profile '{data.get('profile', '?')}'."
