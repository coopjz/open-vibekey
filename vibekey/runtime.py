import copy
import os
import shutil
import threading
import time

from .actions import ActionRunner
from .config import CONTROLS, ConfigStore
from .device import Device, discover
from .events import EventBus
from .gestures import Gestures
from .text_helper import TextClient
from .uinput import FakeInput, UInput
from .voice import Voice


class Runtime:
    def __init__(self, config=None, simulate=False):
        self.lock = threading.RLock()
        self.store = ConfigStore(config)
        self.bus = EventBus()
        self.simulate = simulate
        self.backend = FakeInput(self.bus) if simulate else UInput()
        self.helper = TextClient()
        self.voice = Voice(lambda: self.store.value["voice"], self.bus, self.deliver_voice)
        self.runner = ActionRunner(self.backend, self.bus, self.deliver_text,
                                   self.switch, self.voice_action, simulate)
        self.gestures = Gestures(self.dispatch, **self.store.value["gestures"])
        self.device = Device(self.raw_event, self.control_event, self.device_status)
        self.overlays = {}
        self.preview_until = 0
        self.last_raw = None
        self.status = {"connected": simulate, "error": None, "battery": None, "online": None}
        self.candidates = []
        self.stop_event = threading.Event()
        self.refresh_requested = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="device-runtime", daemon=True)

    def start(self):
        self.thread.start()

    def bindings(self, control):
        config = self.store.value
        layer = list(self.overlays.values())[-1] if self.overlays else config["active_layer"]
        layers = config["profiles"][config["active_profile"]]["layers"]
        result = {}
        for trigger, action in layers[layer]["bindings"].get(control, {}).items():
            index = layer
            while action.get("type") == "inherit" and index > 0:
                index -= 1
                action = layers[index]["bindings"].get(control, {}).get(trigger, {"type": "none"})
            if action.get("type") == "inherit":
                action = {"type": "none"}
            result[trigger] = action
        single = result.get("single", {})
        if single.get("type") in ("voice", "momentary_layer") or single.get("mode") == "hold":
            return {"single": single}
        return result

    def raw_event(self, signature, pressed, pulse):
        with self.lock:
            if pressed:
                self.last_raw = signature
            self.bus.publish("raw", signature=signature, pressed=pressed, pulse=pulse)
            control = self.store.value["device"]["mapping"].get(signature)
            if control:
                if control in ("cw", "ccw"):
                    if pressed:
                        self.control_event(control, True, True)
                else:
                    self.control_event(control, pressed, pulse)

    def control_event(self, control, pressed, pulse=False):
        if control not in CONTROLS:
            raise ValueError("Unknown control")
        with self.lock:
            self.bus.publish("control", control=control, pressed=pressed, pulse=pulse)
            if self.store.error or self.preview_until > time.monotonic():
                return
            if not self.simulate and not self.device.selected:
                return
            self.gestures.edge(control, pressed, self.bindings(control), pulse)

    def dispatch(self, control, action, edge):
        kind = action["type"]
        self.bus.publish("gesture", control=control, gesture=edge, action=kind)
        if kind == "momentary_layer":
            if edge == "press":
                self.overlays[control] = action["index"]
            else:
                self.overlays.pop(control, None)
            self.bus.publish("state_changed")
        elif kind == "voice" and action.get("operation") == "ptt":
            if not self.simulate:
                self.voice.start() if edge == "press" else self.voice.stop()
            else:
                self.bus.publish("simulated_action", action="voice_" + edge)
        elif kind in ("layer", "profile"):
            # Layer changes must take effect before the next physical edge.
            self.switch(action)
        elif kind == "voice":
            self.voice_action(action["operation"])
        elif kind == "shortcut" and action.get("mode") == "hold":
            self.backend.hold_shortcut(action["keys"], edge == "press", control)
        else:
            self.runner.submit(copy.deepcopy(action))

    def voice_action(self, operation):
        if operation == "cancel":
            self.runner.cancel()
            self.voice.cancel()
        elif operation == "confirm":
            self.voice.confirm()

    def switch(self, action):
        with self.lock:
            self.gestures.reset()
            self.overlays.clear()
            if action["type"] == "profile":
                if action["id"] not in self.store.value["profiles"]:
                    raise ValueError("Unknown profile")
                self.store.value["active_profile"] = action["id"]
                self.store.value["active_layer"] = 0
            else:
                self.store.value["active_layer"] = action["index"]
            self.bus.publish("state_changed")

    def deliver_text(self, text, insert=True, cancelled=None):
        if self.simulate:
            self.bus.publish("simulated_action", action="text")
            return
        x11 = os.environ.get("XDG_SESSION_TYPE") == "x11"
        self.helper.send(text, show=not (x11 and insert))
        if x11 and insert:
            if cancelled:
                if cancelled.wait(0.1):
                    return
            else:
                time.sleep(0.1)
            self.backend.shortcut("CTRL+V", cancelled)
        else:
            self.bus.publish("notice", message="Text copied; paste manually in the target application")

    def deliver_voice(self, text):
        self.deliver_text(text, insert=True)

    def device_status(self, event):
        with self.lock:
            if event["kind"] == "battery":
                self.status["battery"] = event
            elif event["kind"] == "online":
                self.status["online"] = event["online"]
                if not event["online"]:
                    self.cancel()
            self.bus.publish("device", **event)

    def cancel(self):
        self.gestures.reset()
        self.overlays.clear()
        self.runner.cancel()
        self.voice.cancel()

    def preview(self, seconds):
        if type(seconds) not in (int, float) or not 0 <= seconds <= 30:
            raise ValueError("Preview lease must be 0..30 seconds")
        with self.lock:
            self.cancel()
            self.preview_until = time.monotonic() + seconds if seconds else 0
            self.bus.publish("state_changed")

    def save(self, value):
        with self.lock:
            # Validate and persist before changing the running configuration.
            self.store.save(value)
            self.cancel()
            self.gestures = Gestures(self.dispatch, **self.store.value["gestures"])
            self.refresh_requested.set()
            self.bus.publish("state_changed")

    def state(self):
        with self.lock:
            return {
                "simulate": self.simulate, "device": copy.deepcopy(self.status),
                "devices": copy.deepcopy(self.candidates),
                "selected": copy.deepcopy(self.device.selected),
                "config_error": self.store.error,
                "active_profile": self.store.value["active_profile"],
                "active_layer": list(self.overlays.values())[-1] if self.overlays else self.store.value["active_layer"],
                "preview": self.preview_until > time.monotonic(),
                "last_raw": self.last_raw, "voice": self.voice.snapshot(),
            }

    def capabilities(self):
        return {
            "session": os.environ.get("XDG_SESSION_TYPE", "unknown"),
            "uinput_access": os.access("/dev/uinput", os.W_OK),
            "parec": bool(shutil.which("parec")),
            "whisper": bool(shutil.which(self.store.value["voice"]["whisper_executable"])),
            "automatic_paste": os.environ.get("XDG_SESSION_TYPE") == "x11",
            "application_focus": os.environ.get("XDG_SESSION_TYPE") == "x11" and bool(shutil.which("wmctrl")),
            "wayland_text": "clipboard-and-manual-paste",
            "hardware_writes": {
                "brightness": "unverified-disabled", "lights": "unverified-disabled",
                "key_tables": "unverified-disabled", "studio_heartbeat": "disabled",
            },
            "battery": "passive-vendor-reports-only",
            "languages": {"core": "Python 3.8+", "ui": "JavaScript / HTML / CSS",
                          "text_helper": "Python / GTK3", "offline_asr": "C/C++ whisper.cpp (external)"},
        }

    def _loop(self):
        next_scan = 0
        while not self.stop_event.wait(0.01):
            with self.lock:
                now = time.monotonic()
                try:
                    if self.refresh_requested.is_set():
                        self.refresh_requested.clear()
                        self.cancel()
                        self.device.close()
                        next_scan = 0
                    if not self.simulate:
                        if now >= next_scan:
                            next_scan = now + 3
                            self.candidates = discover()
                            if not self.device.selected and not self.store.error:
                                self.device.connect(self.candidates, self.store.value["device"])
                                self.status.update(connected=True, error=None, battery=None, online=None)
                                self.bus.publish("state_changed")
                        self.device.poll()
                    self.gestures.tick()
                    if self.preview_until and now >= self.preview_until:
                        self.preview_until = 0
                        self.bus.publish("state_changed")
                except OSError as exc:
                    changed = self.status["connected"] or self.status["error"] != str(exc)
                    self.cancel()
                    self.device.close()
                    self.status.update(connected=False, error=str(exc), battery=None, online=None)
                    if changed:
                        self.bus.publish("state_changed")
            self.voice.tick()

    def close(self):
        self.stop_event.set()
        if self.thread.is_alive():
            self.thread.join(timeout=4)
        with self.lock:
            self.cancel()
            self.device.close()
        self.voice.close()
        self.runner.close()
        self.helper.close()
