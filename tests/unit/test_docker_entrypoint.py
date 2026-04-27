"""Tests for the Docker runtime entrypoint."""

from __future__ import annotations

from pathlib import Path

import pytest

from saudi_open_data_mcp import docker_entrypoint


def test_command_from_args_preserves_existing_cli_entrypoint() -> None:
    assert docker_entrypoint.command_from_args(
        ["saudi-open-data-mcp", "--version"]
    ) == ["saudi-open-data-mcp", "--version"]


def test_command_from_args_prefixes_docker_cmd_arguments() -> None:
    assert docker_entrypoint.command_from_args(["run-http"]) == [
        "saudi-open-data-mcp",
        "run-http",
    ]


def test_prepare_state_volume_chowns_existing_registry_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_root = tmp_path / "state"
    registry_path = state_root / "registry.sqlite"
    snapshots_dir = state_root / "snapshots"
    registry_path.parent.mkdir()
    registry_path.write_text("", encoding="utf-8")
    snapshots_dir.mkdir()

    chowned_paths: list[Path] = []

    def fake_chown(path: Path, uid: int, gid: int) -> None:
        assert uid == docker_entrypoint.APP_UID
        assert gid == docker_entrypoint.APP_GID
        chowned_paths.append(path)

    monkeypatch.setattr(docker_entrypoint, "_chown_no_follow", fake_chown)

    docker_entrypoint.prepare_state_volume(state_root)

    assert state_root in chowned_paths
    assert registry_path in chowned_paths
    assert snapshots_dir in chowned_paths


def test_main_repairs_volume_and_drops_privileges_before_exec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str | tuple[str, str, list[str]]] = []

    monkeypatch.setattr(docker_entrypoint.os, "getuid", lambda: 0)
    monkeypatch.setattr(
        docker_entrypoint,
        "prepare_state_volume",
        lambda: events.append("prepare"),
    )
    monkeypatch.setattr(
        docker_entrypoint,
        "drop_privileges",
        lambda: events.append("drop"),
    )
    monkeypatch.setattr(docker_entrypoint.sys, "argv", ["python", "run-http"])

    def fake_execvp(command: str, args: list[str]) -> None:
        events.append(("exec", command, args))
        raise SystemExit(0)

    monkeypatch.setattr(docker_entrypoint.os, "execvp", fake_execvp)

    with pytest.raises(SystemExit) as exc_info:
        docker_entrypoint.main()

    assert exc_info.value.code == 0
    assert events == [
        "prepare",
        "drop",
        ("exec", "saudi-open-data-mcp", ["saudi-open-data-mcp", "run-http"]),
    ]


def test_main_reports_state_preparation_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(docker_entrypoint.os, "getuid", lambda: 0)
    monkeypatch.setattr(docker_entrypoint.sys, "argv", ["python", "run-http"])

    def fail_prepare_state_volume() -> None:
        raise PermissionError("readonly state volume")

    monkeypatch.setattr(
        docker_entrypoint,
        "prepare_state_volume",
        fail_prepare_state_volume,
    )

    with pytest.raises(SystemExit) as exc_info:
        docker_entrypoint.main()

    assert exc_info.value.code == 1
    assert (
        "docker entrypoint failed to prepare runtime state: readonly state volume"
        in capsys.readouterr().err
    )
