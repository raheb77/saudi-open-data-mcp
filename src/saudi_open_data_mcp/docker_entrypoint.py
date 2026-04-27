"""Docker entrypoint for mounted runtime state ownership repair."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

APP_COMMAND = "saudi-open-data-mcp"
APP_UID = 10001
APP_GID = 10001
STATE_ROOT = Path("/var/lib/saudi-open-data-mcp")


def command_from_args(args: Sequence[str]) -> list[str]:
    """Return the CLI command represented by Docker CMD arguments."""

    command_args = list(args) or ["run-http"]
    if command_args[0] == APP_COMMAND:
        return command_args
    return [APP_COMMAND, *command_args]


def prepare_state_volume(
    root: Path = STATE_ROOT,
    *,
    uid: int = APP_UID,
    gid: int = APP_GID,
) -> None:
    """Ensure the mounted Docker state volume is writable by the app user."""

    root.mkdir(parents=True, exist_ok=True)
    _chown_no_follow(root, uid=uid, gid=gid)

    for directory, dirnames, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in (*dirnames, *filenames):
            try:
                _chown_no_follow(directory_path / name, uid=uid, gid=gid)
            except FileNotFoundError:
                continue


def drop_privileges(*, uid: int = APP_UID, gid: int = APP_GID) -> None:
    """Drop the Docker entrypoint from root to the runtime app identity."""

    try:
        os.setgroups([])
    except (AttributeError, PermissionError):
        pass
    os.setgid(gid)
    os.setuid(uid)


def main() -> NoReturn:
    """Repair Docker state ownership, drop privileges, and exec the CLI."""

    command = command_from_args(sys.argv[1:])
    if os.getuid() == 0:
        try:
            prepare_state_volume()
            drop_privileges()
        except OSError as exc:
            _fail(f"docker entrypoint failed to prepare runtime state: {exc}")

    try:
        os.execvp(command[0], command)
    except OSError as exc:
        _fail(f"docker entrypoint failed to execute {command[0]}: {exc}")


def _chown_no_follow(path: Path, *, uid: int, gid: int) -> None:
    os.chown(path, uid, gid, follow_symlinks=False)


def _fail(message: str) -> NoReturn:
    sys.stderr.write(f"{message}\n")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
