"""Core tracking and symlink logic for dotman."""

import hashlib
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotman.config import (
    get_dotfiles_dir,
    load_config,
    load_state,
    save_state,
    DOTMAN_HOME,
)


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def resolve_home(path: str) -> Path:
    # Use absolute() not resolve() to avoid following symlinks when building keys
    return Path(path).expanduser().absolute()


def relative_key(path: Path) -> str:
    home = Path.home()
    try:
        return str(path.relative_to(home))
    except ValueError:
        return str(path)


def track_file(source: Path, profile: str = "default") -> Tuple[bool, str]:
    """Move source file into dotfiles_dir and create a symlink back."""
    cfg = load_config()
    state = load_state()
    dotfiles_dir = get_dotfiles_dir(cfg)
    dotfiles_dir.mkdir(parents=True, exist_ok=True)

    source = source.absolute()
    if not source.exists():
        return False, f"File not found: {source}"

    if source.is_symlink():
        return False, f"Already a symlink: {source}"

    key = relative_key(source)
    profile_dir = dotfiles_dir / profile
    profile_dir.mkdir(parents=True, exist_ok=True)

    dest = profile_dir / key.lstrip(os.sep)
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() or dest.is_symlink():
        return False, f"Already tracked at {dest}"

    shutil.move(str(source), str(dest))
    source.symlink_to(dest)

    tracked = state.setdefault("tracked", {})
    tracked[key] = {
        "source": str(source),
        "dest": str(dest),
        "profile": profile,
        "tracked_at": datetime.utcnow().isoformat(),
        "hash": _file_hash(dest),
    }
    symlinks = state.setdefault("symlinks", {})
    symlinks[str(source)] = str(dest)
    save_state(state)
    return True, f"Tracked: {source} → {dest}"


def untrack_file(source: Path) -> Tuple[bool, str]:
    """Remove symlink and restore original file."""
    state = load_state()
    source = source.absolute()
    key = relative_key(source)

    tracked = state.get("tracked", {})
    if key not in tracked:
        return False, f"Not tracked: {source}"

    entry = tracked[key]
    dest = Path(entry["dest"])

    if source.is_symlink():
        source.unlink()
    elif source.exists():
        return False, f"Source exists but is not a symlink: {source}"

    if dest.exists():
        shutil.move(str(dest), str(source))

    del tracked[key]
    symlinks = state.get("symlinks", {})
    symlinks.pop(str(source), None)
    save_state(state)
    return True, f"Untracked and restored: {source}"


def list_tracked(profile: Optional[str] = None) -> List[Dict]:
    state = load_state()
    entries = list(state.get("tracked", {}).values())
    if profile:
        entries = [e for e in entries if e.get("profile") == profile]
    return entries


def check_status(entry: Dict) -> str:
    source = Path(entry["source"])
    dest = Path(entry["dest"])

    if not dest.exists():
        return "missing-dest"
    if not source.exists() and not source.is_symlink():
        return "missing-link"
    if source.is_symlink() and os.readlink(source) == str(dest):
        current_hash = _file_hash(dest)
        if current_hash != entry.get("hash", ""):
            return "modified"
        return "ok"
    if source.exists() and not source.is_symlink():
        return "conflict"
    return "broken-link"


def restore_symlinks(profile: Optional[str] = None, dry_run: bool = False) -> List[Tuple[str, str]]:
    """Re-create symlinks for all tracked files."""
    state = load_state()
    results = []
    for key, entry in state.get("tracked", {}).items():
        if profile and entry.get("profile") != profile:
            continue
        source = Path(entry["source"])
        dest = Path(entry["dest"])

        if not dest.exists():
            results.append((key, "skip — dest missing"))
            continue

        if source.is_symlink() and os.readlink(source) == str(dest):
            results.append((key, "already linked"))
            continue

        if source.exists() and not source.is_symlink():
            results.append((key, "skip — file exists (conflict)"))
            continue

        if not dry_run:
            source.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink():
                source.unlink()
            source.symlink_to(dest)
        results.append((key, "restored" if not dry_run else "would restore"))
    return results


def backup_file(key: str) -> Tuple[bool, str]:
    state = load_state()
    tracked = state.get("tracked", {})
    if key not in tracked:
        return False, f"Not tracked: {key}"
    entry = tracked[key]
    dest = Path(entry["dest"])
    if not dest.exists():
        return False, "Dest file missing"

    backup_dir = DOTMAN_HOME / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    backup_name = f"{key.replace(os.sep, '_').lstrip('_')}_{ts}"
    backup_path = backup_dir / backup_name
    shutil.copy2(str(dest), str(backup_path))
    return True, str(backup_path)


def diff_file(key: str) -> str:
    """Return unified diff between current and last-known state."""
    state = load_state()
    tracked = state.get("tracked", {})
    if key not in tracked:
        return f"Not tracked: {key}"
    entry = tracked[key]
    dest = Path(entry["dest"])
    if not dest.exists():
        return "Dest file missing"

    backup_dir = DOTMAN_HOME / "backups"
    backups = sorted(backup_dir.glob(f"{key.replace(os.sep, '_').lstrip('_')}_*"))
    if not backups:
        return "No backup to diff against. Run `dotman backup` first."

    latest = backups[-1]
    result = subprocess.run(
        ["diff", "-u", str(latest), str(dest)],
        capture_output=True,
        text=True,
    )
    return result.stdout or "(no differences)"
