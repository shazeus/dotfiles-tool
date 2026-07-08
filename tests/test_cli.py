from pathlib import Path

from click.testing import CliRunner

import dotman.cli as cli_module
import dotman.config as config_module


def _set_dotman_home(monkeypatch, root: Path) -> Path:
    dotman_home = root / ".config" / "dotman"
    monkeypatch.setattr(config_module, "DOTMAN_HOME", dotman_home)
    monkeypatch.setattr(config_module, "CONFIG_FILE", dotman_home / "config.json")
    monkeypatch.setattr(config_module, "STATE_FILE", dotman_home / "state.json")
    monkeypatch.setattr(cli_module, "DOTMAN_HOME", dotman_home)
    return dotman_home


def test_status_profile_filters(monkeypatch, tmp_path):
    runner = CliRunner()
    home = tmp_path / "home"
    home.mkdir()
    _set_dotman_home(monkeypatch, home)

    work_file = home / ".config" / "work-tool.conf"
    work_file.parent.mkdir(parents=True)
    work_file.write_text("key=value\n")

    default_file = home / ".zshrc"
    default_file.write_text("export PATH=/usr/bin\n")

    env = {"HOME": str(home)}
    dotfiles_dir = home / ".dotfiles"

    result = runner.invoke(cli_module.cli, ["init", "--dir", str(dotfiles_dir)], env=env)
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli_module.cli,
        ["track", str(work_file), "--profile", "work"],
        env=env,
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli_module.cli, ["track", str(default_file)], env=env)
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli_module.cli,
        ["status", "--profile", "work"],
        env=env,
    )
    assert result.exit_code == 0, result.output
    assert "Profile scope:" in result.output
    assert "work" in result.output
    assert "Tracked files:" in result.output
    assert "1 total" in result.output

    result = runner.invoke(cli_module.cli, ["status", "--all-profiles"], env=env)
    assert result.exit_code == 0, result.output
    assert "all profiles" in result.output
    assert "2 total" in result.output


def test_profile_create_list_and_switch_require_existing_profile(monkeypatch, tmp_path):
    runner = CliRunner()
    home = tmp_path / "home"
    home.mkdir()
    _set_dotman_home(monkeypatch, home)

    env = {"HOME": str(home)}
    dotfiles_dir = home / ".dotfiles"

    result = runner.invoke(cli_module.cli, ["init", "--dir", str(dotfiles_dir)], env=env)
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli_module.cli, ["profile", "create", "work"], env=env)
    assert result.exit_code == 0, result.output
    assert "Profile 'work' created" in result.output

    result = runner.invoke(cli_module.cli, ["profile", "list"], env=env)
    assert result.exit_code == 0, result.output
    assert "work" in result.output
    assert ".git" not in result.output

    result = runner.invoke(cli_module.cli, ["profile", "switch", "missing"], env=env)
    assert result.exit_code == 1, result.output
    assert "does not exist" in result.output
