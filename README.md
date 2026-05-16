<p align="center">
  <h1 align="center">dotman</h1>
  <p align="center">Dotfile manager — track, sync, and restore config files across machines.</p>
  <p align="center">
    <a href="https://pypi.org/project/dotfiles-tool/"><img src="https://img.shields.io/pypi/v/dotfiles-tool?color=blue&label=PyPI" alt="PyPI"></a>
    <a href="https://pypi.org/project/dotfiles-tool/"><img src="https://img.shields.io/pypi/pyversions/dotfiles-tool" alt="Python"></a>
    <a href="https://github.com/shazeus/dotfiles-tool/blob/main/LICENSE"><img src="https://img.shields.io/github/license/shazeus/dotfiles-tool" alt="License"></a>
    <a href="https://github.com/shazeus/dotfiles-tool/stargazers"><img src="https://img.shields.io/github/stars/shazeus/dotfiles-tool?style=social" alt="Stars"></a>
  </p>
</p>

---

**dotman** is a fast, terminal-native dotfile manager that keeps your configuration files in sync across all your machines. It moves tracked files into a central dotfiles directory, creates symlinks at their original locations, and uses git to sync changes. Profiles let you maintain separate file sets for work, home, and server environments — all protected by optional AES-256-GCM encryption for sensitive configs.

- **Symlink management** — Move files to your dotfiles repo; symlinks stay in place transparently
- **Git sync** — Commit, push, and pull with a single command to keep machines in sync
- **Profiles** — Separate dotfile sets for `work`, `home`, `server`, or any context
- **Diff view** — See exactly what changed since your last backup
- **Backup & restore** — Timestamped snapshots; one command to restore all symlinks on a fresh machine
- **AES-256-GCM encryption** — Protect sensitive files (SSH keys, API tokens) at rest
- **Rich terminal UI** — Color-coded status tables, panels, and progress output

## Installation

```bash
pip install dotfiles-tool
```

## Usage

```bash
# Initialize dotman
dotman init --dir ~/.dotfiles

# Start tracking config files
dotman track ~/.bashrc ~/.vimrc ~/.tmux.conf

# Check status
dotman status
dotman list

# Sync to remote
dotman sync --init --remote git@github.com:you/dotfiles.git
dotman sync --push -m "add tmux config"

# Set up on a new machine
git clone git@github.com:you/dotfiles.git ~/.dotfiles
dotman restore

# Encrypt sensitive files
dotman encrypt ~/.ssh/config --password mysecret
dotman decrypt ~/.ssh/config.enc --password mysecret
```

## Commands

| Command | Description |
|---------|-------------|
| `dotman init` | Initialize dotfiles directory and git repo |
| `dotman track <files>` | Track file(s) — move to dotfiles dir and create symlinks |
| `dotman untrack <files>` | Remove tracking and restore files to original location |
| `dotman list` | List all tracked files with status |
| `dotman status` | Show overall status: tracked count, git state, profile |
| `dotman restore` | Re-create symlinks (use on a fresh machine after cloning) |
| `dotman diff <file>` | Show diff between current file and last backup |
| `dotman backup [files]` | Create timestamped backups of tracked files |
| `dotman sync` | Commit + push (or pull) dotfiles via git |
| `dotman log` | Show git commit history of dotfiles repo |
| `dotman profile list` | List all profiles |
| `dotman profile create <name>` | Create a new profile |
| `dotman profile switch <name>` | Switch active profile |
| `dotman profile delete <name>` | Delete a profile |
| `dotman profile export <name> <file>` | Export profile manifest to JSON |
| `dotman profile import <file>` | Import profile manifest |
| `dotman encrypt <file>` | Encrypt a file with AES-256-GCM |
| `dotman decrypt <file>` | Decrypt a dotman-encrypted file |

## Configuration

dotman stores its config at `~/.config/dotman/config.json`:

```json
{
  "dotfiles_dir": "~/.dotfiles",
  "git_remote": "git@github.com:you/dotfiles.git",
  "active_profile": "default",
  "encrypt_secrets": false
}
```

Override the config location with `DOTMAN_HOME`:

```bash
export DOTMAN_HOME=/custom/path
```

## Profiles

Profiles let you group dotfiles by context:

```bash
dotman profile create work
dotman track ~/.config/work-tool.conf --profile work

dotman profile create server
dotman track ~/.nanorc --profile server

# Switch active profile
dotman profile switch work

# Export/import for sharing
dotman profile export work work-manifest.json
dotman profile import work-manifest.json
```

## License

MIT © [shazeus](https://github.com/shazeus)
