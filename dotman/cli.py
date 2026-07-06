"""dotman CLI — Dotfile manager with symlinks, git sync, profiles, and encryption."""

import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from dotman import __version__
from dotman.config import (
    DOTMAN_HOME,
    get_dotfiles_dir,
    load_config,
    save_config,
)
from dotman.tracker import (
    backup_file,
    check_status,
    diff_file,
    list_tracked,
    resolve_home,
    restore_symlinks,
    track_file,
    untrack_file,
)
from dotman.git_sync import (
    commit_changes,
    get_git_log,
    get_git_status,
    init_repo,
    pull_changes,
    push_changes,
    set_remote,
)
from dotman.profiles import (
    create_profile,
    delete_profile,
    export_profile,
    get_active_profile,
    import_profile,
    list_profiles,
    switch_profile,
)
from dotman.encryption import decrypt_file, encrypt_file, is_encrypted

console = Console()
err_console = Console(stderr=True)

STATUS_COLORS = {
    "ok": "green",
    "modified": "yellow",
    "conflict": "red",
    "broken-link": "red",
    "missing-dest": "red",
    "missing-link": "orange1",
}

STATUS_ICONS = {
    "ok": "✓",
    "modified": "~",
    "conflict": "!",
    "broken-link": "✗",
    "missing-dest": "✗",
    "missing-link": "?",
}


def _print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def _print_error(msg: str) -> None:
    err_console.print(f"[bold red]✗[/bold red] {msg}")


def _print_info(msg: str) -> None:
    console.print(f"[bold cyan]ℹ[/bold cyan] {msg}")


def _print_warning(msg: str) -> None:
    console.print(f"[bold yellow]⚠[/bold yellow] {msg}")


@click.group()
@click.version_option(__version__, prog_name="dotman")
def cli() -> None:
    """dotman — Dotfile manager.

    Track, sync, and restore config files across machines using
    symlinks, git, profiles, and optional encryption.
    """
    pass


# ─── track ────────────────────────────────────────────────────────────────────

@cli.command("track")
@click.argument("files", nargs=-1, required=True)
@click.option("-p", "--profile", default=None, help="Profile to add the file to.")
def cmd_track(files: tuple, profile: Optional[str]) -> None:
    """Track one or more config files.

    Moves the file(s) into your dotfiles directory and creates
    a symlink at the original location.

    \b
    Examples:
      dotman track ~/.bashrc
      dotman track ~/.vimrc ~/.tmux.conf -p work
    """
    if profile is None:
        profile = get_active_profile()
    errors = 0
    for f in files:
        path = resolve_home(f)
        ok, msg = track_file(path, profile)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            errors += 1
    if errors:
        sys.exit(1)


# ─── untrack ──────────────────────────────────────────────────────────────────

@cli.command("untrack")
@click.argument("files", nargs=-1, required=True)
def cmd_untrack(files: tuple) -> None:
    """Untrack file(s) and restore them to their original location.

    Removes the symlink and moves the file back from the dotfiles directory.
    """
    errors = 0
    for f in files:
        path = resolve_home(f)
        ok, msg = untrack_file(path)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            errors += 1
    if errors:
        sys.exit(1)


# ─── list ─────────────────────────────────────────────────────────────────────

@cli.command("list")
@click.option("-p", "--profile", default=None, help="Filter by profile.")
@click.option("--all-profiles", is_flag=True, help="Show files across all profiles.")
def cmd_list(profile: Optional[str], all_profiles: bool) -> None:
    """List all tracked dotfiles with their status.

    \b
    Status codes:
      ✓ ok          — symlink intact, file unchanged
      ~ modified    — file has been modified since last backup
      ! conflict    — real file exists instead of symlink
      ✗ broken-link — symlink points to missing dest
      ? missing-link — link does not exist
    """
    if not all_profiles and profile is None:
        profile = get_active_profile()
    entries = list_tracked(profile if not all_profiles else None)

    if not entries:
        _print_info(
            f"No tracked files"
            + (f" in profile '{profile}'" if profile and not all_profiles else "")
            + "."
        )
        return

    table = Table(
        title=f"Tracked Dotfiles"
        + (f"  [dim](profile: {profile})[/dim]" if profile and not all_profiles else ""),
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold cyan",
    )
    table.add_column("File", style="bold white", no_wrap=False)
    table.add_column("Profile", style="cyan", width=10)
    table.add_column("Status", width=14)
    table.add_column("Dest", style="dim")

    for entry in sorted(entries, key=lambda e: e.get("source", "")):
        status = check_status(entry)
        color = STATUS_COLORS.get(status, "white")
        icon = STATUS_ICONS.get(status, "?")
        status_text = Text(f"{icon} {status}", style=color)
        source = entry.get("source", "?")
        home_str = str(Path.home())
        if source.startswith(home_str):
            source = "~" + source[len(home_str):]
        dest = entry.get("dest", "?")
        if dest.startswith(home_str):
            dest = "~" + dest[len(home_str):]
        table.add_row(source, entry.get("profile", "default"), status_text, dest)

    console.print(table)


# ─── status ───────────────────────────────────────────────────────────────────

@cli.command("status")
@click.option("-p", "--profile", default=None, help="Show status for only this profile.")
@click.option("--all-profiles", is_flag=True, help="Show status across all profiles.")
def cmd_status(profile: Optional[str], all_profiles: bool) -> None:
    """Show overall status: tracked files, git state, and active profile."""
    cfg = load_config()
    dotfiles_dir = get_dotfiles_dir(cfg)
    if not all_profiles and profile is None:
        profile = get_active_profile()
    entries = list_tracked(profile if not all_profiles else None)

    ok_count = sum(1 for e in entries if check_status(e) == "ok")
    mod_count = sum(1 for e in entries if check_status(e) == "modified")
    err_count = len(entries) - ok_count - mod_count
    git_status = get_git_status(dotfiles_dir)
    if all_profiles:
        profile_scope = "all profiles"
    else:
        profile_scope = profile or "default"

    panel_lines = [
        f"[bold]Dotfiles dir:[/bold]  {dotfiles_dir}",
        f"[bold]Active profile:[/bold] {get_active_profile()}",
        f"[bold]Profile scope:[/bold] {profile_scope}",
        f"[bold]Config file:[/bold]   {DOTMAN_HOME / 'config.json'}",
        "",
        f"[bold]Tracked files:[/bold] {len(entries)} total  "
        f"[green]{ok_count} ok[/green]  "
        f"[yellow]{mod_count} modified[/yellow]  "
        f"[red]{err_count} issues[/red]",
        "",
        f"[bold]Git status:[/bold]    {git_status}",
        f"[bold]Remote:[/bold]        {cfg.get('git_remote') or '(not set)'}",
    ]

    console.print(
        Panel(
            "\n".join(panel_lines),
            title="[bold cyan]dotman status[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )


# ─── restore ──────────────────────────────────────────────────────────────────

@cli.command("restore")
@click.option("-p", "--profile", default=None, help="Restore only this profile.")
@click.option("--dry-run", is_flag=True, help="Show what would be done without doing it.")
def cmd_restore(profile: Optional[str], dry_run: bool) -> None:
    """Restore symlinks for tracked dotfiles.

    Useful when setting up a new machine or after a system reinstall.
    """
    if profile is None:
        profile = get_active_profile()

    results = restore_symlinks(profile=profile, dry_run=dry_run)
    if not results:
        _print_info("Nothing to restore.")
        return

    table = Table(box=box.SIMPLE, header_style="bold cyan")
    table.add_column("File")
    table.add_column("Result")

    for key, msg in results:
        home_str = str(Path.home())
        display = "~" + key if not key.startswith("~") else key
        color = "green" if "restore" in msg else "yellow" if "already" in msg else "red"
        table.add_row(display, Text(msg, style=color))

    if dry_run:
        console.print("[bold yellow]DRY RUN — no changes made[/bold yellow]")
    console.print(table)


# ─── diff ─────────────────────────────────────────────────────────────────────

@cli.command("diff")
@click.argument("file")
def cmd_diff(file: str) -> None:
    """Show diff between current file and its last backup.

    Run `dotman backup` first to create a baseline snapshot.
    """
    path = resolve_home(file)
    from dotman.tracker import relative_key
    key = relative_key(path)
    output = diff_file(key)
    if not output.startswith("(no diff") and output.startswith("---"):
        console.print(
            Panel(output, title=f"[bold]diff: {key}[/bold]", border_style="yellow")
        )
    else:
        console.print(output)


# ─── backup ───────────────────────────────────────────────────────────────────

@cli.command("backup")
@click.argument("files", nargs=-1)
@click.option("-p", "--profile", default=None, help="Backup all files in a profile.")
def cmd_backup(files: tuple, profile: Optional[str]) -> None:
    """Create a timestamped backup of tracked file(s).

    With no arguments, backs up all tracked files in the active profile.
    """
    from dotman.tracker import relative_key

    if not files:
        entries = list_tracked(profile or get_active_profile())
        keys = [relative_key(Path(e["source"])) for e in entries]
    else:
        keys = [relative_key(resolve_home(f)) for f in files]

    if not keys:
        _print_info("Nothing to back up.")
        return

    for key in keys:
        ok, msg = backup_file(key)
        if ok:
            _print_success(f"Backed up {key} → {msg}")
        else:
            _print_error(f"{key}: {msg}")


# ─── sync ─────────────────────────────────────────────────────────────────────

@cli.command("sync")
@click.option("--push", "action", flag_value="push", default=True, help="Push to remote.")
@click.option("--pull", "action", flag_value="pull", help="Pull from remote.")
@click.option("-m", "--message", default="dotman: update dotfiles", help="Commit message.")
@click.option("--branch", default="main", help="Git branch.")
@click.option("--init", "do_init", is_flag=True, help="Initialize git repo if needed.")
@click.option("--remote", default=None, help="Set remote URL before syncing.")
def cmd_sync(action: str, message: str, branch: str, do_init: bool, remote: Optional[str]) -> None:
    """Sync dotfiles with a remote git repository.

    \b
    Examples:
      dotman sync --init --remote git@github.com:you/dotfiles.git
      dotman sync --push -m "add tmux config"
      dotman sync --pull
    """
    cfg = load_config()
    dotfiles_dir = get_dotfiles_dir(cfg)

    if do_init:
        ok, msg = init_repo(dotfiles_dir)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            sys.exit(1)

    if remote:
        ok, msg = set_remote(dotfiles_dir, remote)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            sys.exit(1)

    if action == "push":
        ok, msg = commit_changes(dotfiles_dir, message)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            sys.exit(1)

        cfg2 = load_config()
        if not cfg2.get("git_remote"):
            _print_warning("No remote set. Use --remote <url> or `dotman sync --init --remote <url>`.")
            return

        ok, msg = push_changes(dotfiles_dir, branch)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            sys.exit(1)
    else:
        ok, msg = pull_changes(dotfiles_dir, branch)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)
            sys.exit(1)


# ─── log ──────────────────────────────────────────────────────────────────────

@cli.command("log")
@click.option("-n", default=10, help="Number of commits to show.")
def cmd_log(n: int) -> None:
    """Show the git commit history of your dotfiles repo."""
    cfg = load_config()
    dotfiles_dir = get_dotfiles_dir(cfg)
    output = get_git_log(dotfiles_dir, n)
    console.print(
        Panel(output, title="[bold cyan]dotfiles git log[/bold cyan]", border_style="cyan")
    )


# ─── profile ──────────────────────────────────────────────────────────────────

@cli.group("profile")
def cmd_profile() -> None:
    """Manage profiles for grouping dotfiles by context.

    Profiles let you maintain separate sets of dotfiles, e.g.
    'work', 'home', 'server'.
    """
    pass


@cmd_profile.command("list")
def profile_list() -> None:
    """List all profiles."""
    profiles = list_profiles()
    active = get_active_profile()
    table = Table(box=box.SIMPLE, header_style="bold cyan")
    table.add_column("Profile")
    table.add_column("Active")
    for p in profiles:
        active_marker = Text("● active", style="green") if p == active else Text("")
        table.add_row(p, active_marker)
    console.print(table)


@cmd_profile.command("create")
@click.argument("name")
def profile_create(name: str) -> None:
    """Create a new profile."""
    ok, msg = create_profile(name)
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)
        sys.exit(1)


@cmd_profile.command("switch")
@click.argument("name")
def profile_switch(name: str) -> None:
    """Switch the active profile."""
    ok, msg = switch_profile(name)
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)
        sys.exit(1)


@cmd_profile.command("delete")
@click.argument("name")
@click.option("--force", is_flag=True, help="Delete even if it has tracked files.")
def profile_delete(name: str, force: bool) -> None:
    """Delete a profile."""
    ok, msg = delete_profile(name, force)
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)
        sys.exit(1)


@cmd_profile.command("export")
@click.argument("name")
@click.argument("output", type=click.Path())
def profile_export(name: str, output: str) -> None:
    """Export a profile manifest to a JSON file."""
    ok, msg = export_profile(name, Path(output))
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)
        sys.exit(1)


@cmd_profile.command("import")
@click.argument("manifest", type=click.Path(exists=True))
def profile_import(manifest: str) -> None:
    """Import tracked files from a profile manifest."""
    ok, msg = import_profile(Path(manifest))
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)
        sys.exit(1)


# ─── encrypt / decrypt ────────────────────────────────────────────────────────

@cli.command("encrypt")
@click.argument("file")
@click.option("--password", prompt=True, hide_input=True, help="Encryption password.")
@click.option("--in-place", is_flag=True, help="Replace the original file.")
def cmd_encrypt(file: str, password: str, in_place: bool) -> None:
    """Encrypt a dotfile with AES-256-GCM.

    The encrypted file is saved with a `.enc` extension unless
    --in-place is used.
    """
    source = Path(file).expanduser().resolve()
    dest = source.with_suffix(source.suffix + ".enc") if not in_place else source.with_name(source.name + ".enc")
    ok, msg = encrypt_file(source, dest, password)
    if ok:
        _print_success(msg)
        if in_place:
            source.unlink()
            _print_info(f"Original removed: {source}")
    else:
        _print_error(msg)
        sys.exit(1)


@cli.command("decrypt")
@click.argument("file")
@click.option("--password", prompt=True, hide_input=True, help="Decryption password.")
@click.option("--output", default=None, help="Output path (default: strip .enc suffix).")
def cmd_decrypt(file: str, password: str, output: Optional[str]) -> None:
    """Decrypt a dotman-encrypted file."""
    source = Path(file).expanduser().resolve()
    if output:
        dest = Path(output).expanduser().resolve()
    else:
        name = source.name
        if name.endswith(".enc"):
            dest = source.with_name(name[:-4])
        else:
            dest = source.with_name(name + ".dec")
    ok, msg = decrypt_file(source, dest, password)
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)
        sys.exit(1)


# ─── init ─────────────────────────────────────────────────────────────────────

@cli.command("init")
@click.option("--dir", "dotfiles_dir", default=None, help="Path to dotfiles directory.")
@click.option("--remote", default=None, help="Remote git URL.")
def cmd_init(dotfiles_dir: Optional[str], remote: Optional[str]) -> None:
    """Initialize dotman and the dotfiles git repository.

    Sets up the dotfiles directory and optionally initializes a
    git repo with a remote for syncing.

    \b
    Example:
      dotman init --dir ~/.dotfiles --remote git@github.com:you/dotfiles.git
    """
    cfg = load_config()
    if dotfiles_dir:
        cfg["dotfiles_dir"] = str(Path(dotfiles_dir).expanduser().resolve())
        save_config(cfg)
        _print_success(f"Dotfiles directory set to: {cfg['dotfiles_dir']}")

    d = get_dotfiles_dir(cfg)
    ok, msg = init_repo(d)
    if ok:
        _print_success(msg)
    else:
        _print_error(msg)

    if remote:
        ok, msg = set_remote(d, remote)
        if ok:
            _print_success(msg)
        else:
            _print_error(msg)

    console.print(
        Panel(
            f"Dotfiles dir: [cyan]{d}[/cyan]\n"
            f"Config:       [cyan]{DOTMAN_HOME / 'config.json'}[/cyan]\n\n"
            "Next steps:\n"
            "  [bold]dotman track ~/.bashrc ~/.vimrc[/bold]\n"
            "  [bold]dotman sync --push[/bold]",
            title="[bold green]dotman initialized[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
