"""Launch CLI tools in GNOME Terminal windows with stable per-window roles."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

TOOLS = {"codex": ("Codex CLI", "vibekey-codex"),
         "claude": ("Claude Code", "vibekey-claude")}


def executable(tool):
    if tool not in TOOLS:
        raise ValueError("Unknown CLI tool")
    found = shutil.which(tool)
    if found:
        return found
    for directory in (".local/bin", ".npm-global/bin", ".cargo/bin"):
        path = Path.home() / directory / tool
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path)
    return None


def launch(tool, args=(), directory=None):
    command = executable(tool)
    terminal = shutil.which("gnome-terminal")
    if not command or not terminal:
        raise ValueError("请先安装所选 CLI 和 GNOME Terminal")
    name, role = TOOLS[tool]
    # Role belongs to the window and survives the CLI changing its title.
    try:
        subprocess.run([terminal, "--window", "--role=" + role, "--title=" + name,
                      "--working-directory=" + str(directory or Path.home()), "--", command] + list(args),
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=3, check=True)
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise ValueError("无法打开 CLI 终端") from exc


if __name__ == "__main__":
    try:
        launch(sys.argv[1], sys.argv[2:], Path.cwd())
    except (IndexError, ValueError, OSError) as exc:
        raise SystemExit(str(exc))
