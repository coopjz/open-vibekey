"""Minimal Linux uinput keyboard/mouse backend using only the standard library."""
import fcntl
import os
import struct
import threading
import time

# Linux input-event-codes.h ABI.
KEYS = {
    "ESC": 1, "ENTER": 28, "TAB": 15, "SPACE": 57, "BACKSPACE": 14,
    "CTRL": 29, "SHIFT": 42, "ALT": 56, "SUPER": 125, "META": 125,
    "RIGHTCTRL": 97, "RIGHTSHIFT": 54, "RIGHTALT": 100,
    "UP": 103, "DOWN": 108, "LEFT": 105, "RIGHT": 106,
    "HOME": 102, "END": 107, "PAGEUP": 104, "PAGEDOWN": 109,
    "INSERT": 110, "DELETE": 111, "PRINTSCREEN": 99,
    "MUTE": 113, "VOLUMEDOWN": 114, "VOLUMEUP": 115,
    "PLAYPAUSE": 164, "NEXTSONG": 163, "PREVIOUSSONG": 165,
    "LEFTBRACE": 26, "RIGHTBRACE": 27, "SEMICOLON": 39,
    "APOSTROPHE": 40, "GRAVE": 41, "BACKSLASH": 43,
    "COMMA": 51, "DOT": 52, "SLASH": 53, "MINUS": 12, "EQUAL": 13,
    "BTN_LEFT": 272, "BTN_RIGHT": 273, "BTN_MIDDLE": 274,
    "CAPSLOCK": 58, "NUMLOCK": 69, "SCROLLLOCK": 70, "PAUSE": 119,
    "KP0": 82, "KP1": 79, "KP2": 80, "KP3": 81, "KP4": 75,
    "KP5": 76, "KP6": 77, "KP7": 71, "KP8": 72, "KP9": 73,
    "KPDOT": 83, "KPPLUS": 78, "KPMINUS": 74, "KPASTERISK": 55,
    "KPSLASH": 98, "KPENTER": 96,
}
for chars, codes in (
    ("1234567890", range(2, 12)),
    ("QWERTYUIOP", range(16, 26)),
    ("ASDFGHJKL", range(30, 39)),
    ("ZXCVBNM", range(44, 51)),
):
    KEYS.update(zip(chars, codes))
KEYS.update({"F%d" % i: 58 + i for i in range(1, 11)})
KEYS.update({"F11": 87, "F12": 88})
KEYS.update({"F%d" % i: 183 + i - 13 for i in range(13, 25)})
ALIASES = {"CONTROL": "CTRL", "RETURN": "ENTER", "WIN": "SUPER", "ESCAPE": "ESC"}


def parse_shortcut(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Shortcut must be e.g. CTRL+SHIFT+A")
    names = [ALIASES.get(part.strip().upper(), part.strip().upper()) for part in value.split("+")]
    if len(names) > 12 or len(set(names)) != len(names) or any(name not in KEYS for name in names):
        raise ValueError("Unknown or repeated shortcut key")
    return [KEYS[name] for name in names]


class UInput:
    def __init__(self):
        self.fd = None
        self.held = set()
        self.hold_groups = {}
        self.lock = threading.RLock()

    def open(self):
        with self.lock:
            if self.fd is not None:
                return
            fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            try:
                fcntl.ioctl(fd, 0x40045564, 1)  # UI_SET_EVBIT EV_KEY
                fcntl.ioctl(fd, 0x40045564, 2)  # EV_REL
                for code in set(KEYS.values()):
                    fcntl.ioctl(fd, 0x40045565, code)  # UI_SET_KEYBIT
                for axis in (0, 1, 6, 8):
                    fcntl.ioctl(fd, 0x40045566, axis)
                # Legacy uinput_user_dev works on the Ubuntu 20.04 kernel.
                header = struct.pack("80sHHHHI", b"VibeKey virtual input", 3, 0x1209, 0x0001, 1, 0)
                os.write(fd, header + bytes(64 * 4 * 4))
                fcntl.ioctl(fd, 0x5501)  # UI_DEV_CREATE
                self.fd = fd
                time.sleep(0.1)  # allow the compositor to discover the device
            except BaseException:
                os.close(fd)
                raise

    def _event(self, kind, code, value):
        os.write(self.fd, struct.pack("@llHHi", 0, 0, kind, code, value))

    def key(self, code, down):
        with self.lock:
            self.open()
            self._event(1, code, int(down))
            self._event(0, 0, 0)
            if down:
                self.held.add(code)
            else:
                self.held.discard(code)

    def shortcut(self, value, cancel=None):
        codes = parse_shortcut(value)
        with self.lock:
            acquired = []
            try:
                for code in codes:
                    if cancel and cancel.is_set():
                        return
                    if code not in self.held:
                        self.key(code, True)
                        acquired.append(code)
                if cancel:
                    cancel.wait(0.025)
                else:
                    time.sleep(0.025)
            finally:
                for code in reversed(acquired):
                    if code in self.held:
                        self.key(code, False)

    def hold_shortcut(self, value, pressed, owner):
        codes = parse_shortcut(value)
        with self.lock:
            if pressed:
                if owner in self.hold_groups:
                    return
                self.hold_groups[owner] = codes
                try:
                    for code in codes:
                        if code not in self.held:
                            self.key(code, True)
                except BaseException:
                    self.release_all()
                    raise
            else:
                released = self.hold_groups.pop(owner, [])
                remaining = {code for group in self.hold_groups.values() for code in group}
                for code in reversed(released):
                    if code in self.held and code not in remaining:
                        self.key(code, False)

    def release_all(self):
        with self.lock:
            if self.fd is not None:
                for code in list(self.held):
                    self._event(1, code, 0)
                self._event(0, 0, 0)
            self.held.clear()
            self.hold_groups.clear()

    def close(self):
        with self.lock:
            self.release_all()
            if self.fd is not None:
                fcntl.ioctl(self.fd, 0x5502)
                os.close(self.fd)
                self.fd = None


class FakeInput:
    def __init__(self, bus):
        self.bus = bus
        self.held = set()
        self.hold_groups = {}

    def shortcut(self, value, cancel=None):
        parse_shortcut(value)
        if not cancel or not cancel.is_set():
            self.bus.publish("simulated_action", action="shortcut", keys=value)

    def release_all(self):
        self.held.clear()
        self.hold_groups.clear()

    def hold_shortcut(self, value, pressed, owner):
        if pressed:
            self.hold_groups[owner] = parse_shortcut(value)
        else:
            self.hold_groups.pop(owner, None)
        self.held = {code for codes in self.hold_groups.values() for code in codes}
        self.bus.publish("simulated_action", action="shortcut_hold", keys=value, pressed=pressed)

    def close(self):
        self.release_all()
