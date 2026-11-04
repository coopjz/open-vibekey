"""Read X11 window properties; never activate windows or inspect their contents."""
import json
import os
import re
import shutil
import subprocess


def availability():
    if os.environ.get("XDG_SESSION_TYPE") != "x11":
        return False, "自动跟随目前支持 X11 桌面"
    if not shutil.which("xprop"):
        return False, "自动跟随需要 xprop"
    return True, ""


def _query(*args):
    result = subprocess.run(["xprop"] + list(args), stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=0.5, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode:
        raise OSError("无法读取窗口属性")
    return result.stdout


def window_info(window_id):
    if not re.fullmatch(r"0x[0-9a-fA-F]+", window_id):
        raise ValueError("Invalid window ID")
    properties = {}
    for line in _query("-id", window_id, "WM_CLASS", "_NET_WM_NAME", "WM_NAME", "WM_WINDOW_ROLE").splitlines():
        name, separator, value = line.partition(" = ")
        if not separator:
            continue
        strings = []
        # xprop quotes and backslash-escapes STRING/UTF8_STRING values.
        for quoted in re.findall(r'"(?:[^"\\]|\\.)*"', value):
            try:
                strings.append(json.loads(quoted))
            except ValueError:
                strings.append(quoted[1:-1])
        properties[name.split("(", 1)[0]] = strings
    classes = properties.get("WM_CLASS", [])
    return {"id": window_id, "wm_class": ".".join(classes),
            "title": (properties.get("_NET_WM_NAME") or properties.get("WM_NAME") or [""])[0][:512],
            "role": (properties.get("WM_WINDOW_ROLE") or [""])[0][:256]}


def active_window():
    match = re.search(r"window id # (0x[0-9a-fA-F]+)", _query("-root", "_NET_ACTIVE_WINDOW"))
    if not match or int(match[1], 16) == 0:
        return {"id": "", "wm_class": "", "title": "", "role": ""}
    return window_info(match[1])


def windows():
    available, error = availability()
    if not available:
        raise ValueError(error)
    result = []
    for window_id in re.findall(r"0x[0-9a-fA-F]+", _query("-root", "_NET_CLIENT_LIST"))[:128]:
        try:
            item = window_info(window_id)
            if item["wm_class"]:
                result.append(item)
        except (OSError, subprocess.TimeoutExpired):
            continue  # A window may close during enumeration.
    return result


def match_rule(window, rules):
    for rule in rules:
        wanted = rule.get("wm_class", "").casefold()
        actual = window.get("wm_class", "").casefold()
        class_match = not wanted or wanted == actual or wanted in actual.split(".")
        if (class_match and
                rule.get("title", "").casefold() in window.get("title", "").casefold() and
                (not rule.get("role") or rule["role"].casefold() == window.get("role", "").casefold())):
            return rule
    return None


def default_settings(profile):
    return {"enabled": False, "default_profile": profile, "default_layer": 0, "rules": []}
