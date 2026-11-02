"""Read freedesktop application launchers without executing their commands."""
import configparser
import os
import shlex
import shutil
import subprocess
from pathlib import Path


def applications(directories=None):
    desktop_launcher = shutil.which("gtk-launch") if directories is None else None
    if directories is None:
        home = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
        system = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
        directories = [Path(folder) / "applications" for folder in [home] + system]
    found, seen = [], set()
    for directory in directories:
        directory = Path(directory)
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*.desktop")):
            identity = str(path.relative_to(directory)).replace("/", "-")
            if identity in seen:
                continue
            seen.add(identity)
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(str(path), encoding="utf-8")
                entry = parser["Desktop Entry"]
                if entry.get("Type") != "Application" or any(
                    entry.get(key, "").lower() == "true" for key in ("Hidden", "NoDisplay")
                ):
                    continue
                name = entry.get("Name[zh_CN]") or entry.get("Name", path.stem)
                argv = []
                for part in shlex.split(entry.get("Exec", "")):
                    if part == "%c":
                        argv.append(name)
                    elif part == "%k":
                        argv.append(str(path))
                    elif part == "%i":
                        if entry.get("Icon"):
                            argv.extend(["--icon", entry["Icon"]])
                    elif part not in ("%f", "%F", "%u", "%U"):
                        # Unsupported embedded field codes are not safe argv.
                        if "%" in part.replace("%%", ""):
                            raise ValueError("Unsupported desktop field code")
                        argv.append(part.replace("%%", "%"))
                if not argv:
                    continue
                if entry.get("Terminal", "").lower() == "true":
                    terminal = shutil.which("x-terminal-emulator")
                    if not terminal:
                        continue
                    argv = [terminal, "-e"] + argv
                wm_class = entry.get("StartupWMClass", "")
                # gtk-launch respects desktop activation and DBusActivatable.
                # Keep parsed argv for systems without a desktop launcher.
                if desktop_launcher:
                    argv = [desktop_launcher, identity]
                found.append({"id": identity, "name": name, "argv": argv,
                              "wm_class": wm_class})
                if len(found) >= 256:
                    return sorted(found, key=lambda item: item["name"].casefold())
            except (OSError, UnicodeError, KeyError, ValueError, configparser.Error):
                continue
    return sorted(found, key=lambda item: item["name"].casefold())


def focus_application(wm_class):
    """Activate an existing matching X11 window when wmctrl is available."""
    if not wm_class or os.environ.get("XDG_SESSION_TYPE") != "x11" or not shutil.which("wmctrl"):
        return False
    try:
        result = subprocess.run(["wmctrl", "-lx"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=2, text=True)
        for line in result.stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 4:
                continue
            wanted, classes = wm_class.casefold(), parts[3].casefold()
            if not (classes == wanted or classes.startswith(wanted + ".") or classes.endswith("." + wanted)):
                continue
            activated = subprocess.run(["wmctrl", "-ia", parts[0]], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=2)
            return activated.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
    return False
