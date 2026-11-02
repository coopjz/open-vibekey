import copy
import json
import os
import shutil
import tempfile
import re
import urllib.parse
from pathlib import Path

VERSION = 1
CONTROLS = ("top", "middle", "bottom", "knob", "cw", "ccw")
TRIGGERS = ("single", "double", "hold")
ACTION_TYPES = (
    "none", "shortcut", "text", "application", "shell", "volume",
    "macro", "layer", "profile", "momentary_layer", "voice", "inherit",
)


def default_config():
    layers = []
    for index in range(4):
        bindings = {c: {"single": {"type": "none" if index == 0 else "inherit"}} for c in CONTROLS}
        if index == 0:
            bindings.update({
                "top": {"single": {"type": "voice", "operation": "ptt"}},
                "middle": {"single": {"type": "voice", "operation": "confirm"}},
                "bottom": {"single": {"type": "voice", "operation": "cancel"}},
                "knob": {"single": {"type": "volume", "operation": "mute"}},
                "cw": {"single": {"type": "volume", "operation": "up"}},
                "ccw": {"single": {"type": "volume", "operation": "down"}},
            })
        layers.append({"name": "Layer %d" % (index + 1), "bindings": bindings})
    return {
        "version": VERSION,
        "active_profile": "default", "active_layer": 0,
        "profiles": {"default": {"name": "Default", "layers": layers}},
        "gestures": {"double_ms": 250, "hold_ms": 500},
        "device": {
            "serial": "", "usb_path": "", "grab": True, "input_mode": "standard",
            "mapping": {
                "keyboard:00:01": "top", "keyboard:00:28": "middle",
                "keyboard:00:29": "bottom", "keyboard:00:46": "knob",
                "keyboard:00:4f": "cw", "keyboard:00:2a": "ccw",
                "wheel:+": "cw", "wheel:-": "ccw",
            },
        },
        "voice": {
            "backend": "command", "source": "", "max_seconds": 120,
            "timeout_seconds": 180, "auto_insert": False,
            "command": [], "whisper_executable": "whisper-cli",
            "model_path": "", "language": "auto",
            "api_url": "https://api.openai.com/v1/audio/transcriptions",
            "api_model": "whisper-1", "api_key_env": "VIBEKEY_API_KEY",
        },
    }


def _string(value, name, maximum=8192):
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise ValueError("Invalid %s" % name)


def validate_action(action, depth=0):
    if not isinstance(action, dict) or action.get("type") not in ACTION_TYPES:
        raise ValueError("Unknown action type")
    kind = action["type"]
    for field in ("label", "library_id"):
        if field in action:
            _string(action[field], field, 100)
    if kind in ("text", "shell"):
        _string(action.get("value", ""), kind, 65536)
    if kind == "shortcut":
        from .uinput import parse_shortcut
        parse_shortcut(action.get("keys", ""))
        if action.get("mode", "tap") not in ("tap", "hold"):
            raise ValueError("Invalid shortcut output mode")
        if type(action.get("repeat", 1)) is not int or not 1 <= action.get("repeat", 1) <= 20:
            raise ValueError("Shortcut repeat must be 1..20")
        if action.get("mode") == "hold" and (depth or action.get("repeat", 1) != 1):
            raise ValueError("Held shortcuts cannot repeat or be macro steps")
    if kind == "application":
        argv = action.get("argv")
        if not isinstance(argv, list) or not argv or len(argv) > 128:
            raise ValueError("application.argv must be a nonempty array")
        for arg in argv:
            _string(arg, "argument")
        if "wm_class" in action:
            _string(action["wm_class"], "window class", 256)
    if kind == "volume" and action.get("operation") not in ("up", "down", "mute"):
        raise ValueError("Invalid volume operation")
    if kind in ("layer", "momentary_layer"):
        if type(action.get("index")) is not int or not 0 <= action["index"] < 4:
            raise ValueError("Layer must be 0..3")
    if kind == "profile":
        _string(action.get("id"), "profile id", 100)
    if kind == "voice" and action.get("operation") not in ("ptt", "confirm", "cancel"):
        raise ValueError("Invalid voice operation")
    if kind == "macro":
        steps = action.get("steps")
        if depth or not isinstance(steps, list) or len(steps) > 100:
            raise ValueError("Macros must have <=100 steps and cannot nest")
        for step in steps:
            if not isinstance(step, dict):
                raise ValueError("Invalid macro step")
            if "delay_ms" in step:
                if type(step["delay_ms"]) is not int or not 0 <= step["delay_ms"] <= 30000:
                    raise ValueError("Invalid macro delay")
            else:
                validate_action(step, depth + 1)
                if step["type"] in ("voice", "momentary_layer", "inherit"):
                    raise ValueError("Edge actions cannot be macro steps")


def validate(config):
    if not isinstance(config, dict) or type(config.get("version")) is not int or config["version"] != VERSION:
        raise ValueError("Unsupported configuration version")
    profiles = config.get("profiles")
    if not isinstance(profiles, dict) or not 1 <= len(profiles) <= 32:
        raise ValueError("Need 1..32 profiles")
    if config.get("active_profile") not in profiles:
        raise ValueError("Missing active profile")
    if type(config.get("active_layer")) is not int or not 0 <= config["active_layer"] < 4:
        raise ValueError("Invalid active layer")
    for pid, profile in profiles.items():
        _string(pid, "profile id", 100)
        if not isinstance(profile, dict):
            raise ValueError("Invalid profile")
        _string(profile.get("name"), "profile name", 100)
        layers = profile.get("layers")
        if not isinstance(layers, list) or len(layers) != 4:
            raise ValueError("Each profile needs exactly four layers")
        for layer in layers:
            if not isinstance(layer, dict):
                raise ValueError("Invalid layer")
            _string(layer.get("name"), "layer name", 100)
            bindings = layer.get("bindings")
            if not isinstance(bindings, dict) or set(bindings) - set(CONTROLS):
                raise ValueError("Invalid controls")
            for control, gestures in bindings.items():
                if not isinstance(gestures, dict) or set(gestures) - set(TRIGGERS):
                    raise ValueError("Invalid gesture")
                if control in ("cw", "ccw") and set(gestures) - {"single"}:
                    raise ValueError("Rotation only supports single")
                for action in gestures.values():
                    validate_action(action)
                    if action.get("mode") == "hold" and (
                        control in ("cw", "ccw") or len(gestures) != 1 or "single" not in gestures
                    ):
                        raise ValueError("Held shortcuts require a single binding on a button")
                    for item in ([action] + action.get("steps", []) if action["type"] == "macro" else [action]):
                        if item.get("type") == "profile" and item["id"] not in profiles:
                            raise ValueError("Action references missing profile")
                    if action["type"] in ("momentary_layer", "voice") and (
                        len(gestures) != 1 or "single" not in gestures
                    ):
                        raise ValueError("Voice and momentary layer require single binding only")
                    if control in ("cw", "ccw") and (
                        action["type"] == "momentary_layer" or
                        (action["type"] == "voice" and action["operation"] == "ptt")
                    ):
                        raise ValueError("Rotation has no held state")
    library = config.get("library", {})
    if not isinstance(library, dict) or set(library) - {"applications", "macros"}:
        raise ValueError("Invalid action library")
    ids = set()
    for collection, kind in (("applications", "application"), ("macros", "macro")):
        items = library.get(collection, [])
        if not isinstance(items, list) or len(items) > 16:
            raise ValueError("Action library supports at most 16 items per category")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Invalid library item")
            _string(item.get("id"), "library id", 100)
            _string(item.get("name"), "library name", 100)
            if item["id"] in ids or not item["id"] or not item["name"].strip():
                raise ValueError("Invalid or duplicate library identity")
            ids.add(item["id"])
            action = item.get("action")
            validate_action(action)
            if action["type"] != kind:
                raise ValueError("Wrong library action category")
            for step in action.get("steps", []):
                if step.get("type") == "profile" and step["id"] not in profiles:
                    raise ValueError("Library macro references missing profile")
    gestures = config.get("gestures", {})
    if not isinstance(gestures, dict):
        raise ValueError("Invalid gesture settings")
    for key, low, high in (("double_ms", 100, 1000), ("hold_ms", 200, 3000)):
        value = gestures.get(key)
        if type(value) is not int or not low <= value <= high:
            raise ValueError("Invalid %s" % key)
    device = config.get("device", {})
    if not isinstance(device, dict) or device.get("grab") is not True:
        raise ValueError("Exclusive input grab is required")
    for key in ("serial", "usb_path"):
        _string(device.get(key, ""), key, 256)
    if device.get("input_mode", "standard") not in ("standard", "vendor"):
        raise ValueError("Input mode must be standard or vendor")
    mapping = device.get("mapping")
    if not isinstance(mapping, dict) or len(mapping) > 128:
        raise ValueError("Invalid input mapping")
    for signature, control in mapping.items():
        _string(signature, "signature", 100)
        if control not in CONTROLS:
            raise ValueError("Unknown mapped control")
    voice = config.get("voice", {})
    if not isinstance(voice, dict) or voice.get("backend") not in ("command", "whisper", "api"):
        raise ValueError("Unknown transcription backend")
    if set(voice) - set(default_config()["voice"]):
        raise ValueError("Unknown voice setting; credentials belong in environment variables")
    for key in ("source", "model_path", "whisper_executable", "language",
                "api_url", "api_model", "api_key_env"):
        _string(voice.get(key, ""), key)
    for key, upper in (("max_seconds", 120), ("timeout_seconds", 900)):
        if type(voice.get(key)) is not int or not 1 <= voice[key] <= upper:
            raise ValueError("Invalid voice timeout")
    if type(voice.get("auto_insert")) is not bool:
        raise ValueError("Invalid auto_insert")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", voice.get("api_key_env", "")):
        raise ValueError("Invalid API credential environment variable")
    parsed = urllib.parse.urlsplit(voice["api_url"])
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API URL cannot contain credentials, query parameters or fragment")
    if not parsed.hostname or not (parsed.scheme == "https" or (
        parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1", "::1")
    )):
        raise ValueError("API URL must use HTTPS, or HTTP on loopback")
    command = voice.get("command")
    if not isinstance(command, list) or len(command) > 128:
        raise ValueError("Invalid transcription command")
    for arg in command:
        _string(arg, "transcription argument")
    # Credentials belong in the service environment, never JSON or exports.
    if "api_key" in voice:
        raise ValueError("Store API credentials in the named environment variable")
    return config


def migrate(config):
    if not isinstance(config, dict):
        raise ValueError("Configuration must be a JSON object")
    value = copy.deepcopy(config)
    if value.get("version") == 0:
        value["version"] = 1
        defaults = default_config()
        for key in ("voice", "device", "gestures"):
            merged = defaults[key]
            merged.update(value.get(key, {}))
            value[key] = merged
    return validate(value)


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "vibekey" / "config.json"


class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path) if path else config_path()
        self.error = None
        self.value = default_config()
        if self.path.exists():
            try:
                self.value = migrate(json.loads(self.path.read_text(encoding="utf-8")))
            except (ValueError, OSError, TypeError) as exc:
                # Preserve the original and require an explicit save to replace it.
                self.error = "Cannot load configuration: %s" % exc

    def save(self, value):
        value = migrate(value)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temporary = tempfile.mkstemp(prefix=".config-", dir=str(self.path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            if self.path.exists():
                shutil.copy2(str(self.path), str(self.path) + ".bak")
                os.chmod(str(self.path) + ".bak", 0o600)
            os.replace(temporary, str(self.path))
            directory = os.open(str(self.path.parent), os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            self.value, self.error = value, None
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
