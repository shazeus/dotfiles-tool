"""Git-based sync functionality for dotfiles."""

import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from dotman.config import get_dotfiles_dir, load_config, save_config


def _run(cmd: List[str], cwd: Path) -> Tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd))
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def init_repo(dotfiles_dir: Path) -> Tuple[bool, str]:
    dotfiles_dir.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run(["git", "init"], cwd=dotfiles_dir)
    if rc != 0:
        return False, err
    _run(["git", "config", "user.name", "shazeus"], cwd=dotfiles_dir)
    _run(["git", "config", "user.email", "efeborazan07@gmail.com"], cwd=dotfiles_dir)
    gitignore = dotfiles_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text("*.pyc\n__pycache__/\n*.swp\n.DS_Store\n")
    return True, f"Initialized repo at {dotfiles_dir}"


def set_remote(dotfiles_dir: Path, remote_url: str) -> Tuple[bool, str]:
    rc, out, err = _run(["git", "remote", "get-url", "origin"], cwd=dotfiles_dir)
    if rc == 0:
        _run(["git", "remote", "set-url", "origin", remote_url], cwd=dotfiles_dir)
    else:
        rc, out, err = _run(["git", "remote", "add", "origin", remote_url], cwd=dotfiles_dir)
        if rc != 0:
            return False, err
    cfg = load_config()
    cfg["git_remote"] = remote_url
    save_config(cfg)
    return True, f"Remote set to {remote_url}"


def commit_changes(dotfiles_dir: Path, message: str = "dotman: update dotfiles") -> Tuple[bool, str]:
    _run(["git", "add", "-A"], cwd=dotfiles_dir)
    rc, out, err = _run(["git", "commit", "-m", message], cwd=dotfiles_dir)
    if rc != 0:
        if "nothing to commit" in (out + err).lower():
            return True, "Nothing to commit — already up to date."
        return False, err or out
    return True, out


def push_changes(dotfiles_dir: Path, branch: str = "main") -> Tuple[bool, str]:
    rc, out, err = _run(["git", "push", "-u", "origin", branch], cwd=dotfiles_dir)
    if rc != 0:
        return False, err or out
    return True, out or "Pushed successfully."


def pull_changes(dotfiles_dir: Path, branch: str = "main") -> Tuple[bool, str]:
    rc, out, err = _run(["git", "pull", "origin", branch], cwd=dotfiles_dir)
    if rc != 0:
        return False, err or out
    return True, out or "Already up to date."


def get_git_status(dotfiles_dir: Path) -> str:
    if not (dotfiles_dir / ".git").exists():
        return "not-a-repo"
    rc, out, err = _run(["git", "status", "--porcelain"], cwd=dotfiles_dir)
    return out or "clean"


def get_git_log(dotfiles_dir: Path, n: int = 10) -> str:
    rc, out, err = _run(
        ["git", "log", f"-{n}", "--oneline", "--decorate"],
        cwd=dotfiles_dir,
    )
    return out or "(no commits yet)"
