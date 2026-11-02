import copy
import time


class Gestures:
    """Deterministic edge interpreter. Caller serializes access and ticks it."""
    def __init__(self, emit, double_ms=250, hold_ms=500, clock=time.monotonic):
        self.emit = emit
        self.clock = clock
        self.double = double_ms / 1000.0
        self.hold = hold_ms / 1000.0
        self.down = {}
        self.pending = {}

    def reset(self):
        for control, state in list(self.down.items()):
            if state["edge"]:
                self.emit(control, state["bindings"]["single"], "release")
        self.down.clear()
        self.pending.clear()

    def edge(self, control, pressed, bindings, pulse=False):
        now = self.clock()
        self.tick(now)
        if pulse:
            if pressed:
                self.emit(control, bindings.get("single", {"type": "none"}), "single")
            return
        if pressed:
            if control in self.down:
                return
            bindings = copy.deepcopy(bindings)
            single = bindings.get("single", {"type": "none"})
            edge = single["type"] == "momentary_layer" or (
                single["type"] == "voice" and single.get("operation") == "ptt"
            ) or (single["type"] == "shortcut" and single.get("mode") == "hold")
            self.down[control] = {"time": now, "bindings": bindings, "fired": False, "edge": edge}
            if edge:
                self.emit(control, single, "press")
            elif "double" not in bindings and "hold" not in bindings:
                self.down[control]["fired"] = True
                self.emit(control, single, "single")
        else:
            state = self.down.pop(control, None)
            if not state:
                return
            bindings = state["bindings"]
            if state["edge"]:
                self.emit(control, bindings["single"], "release")
            elif not state["fired"]:
                if control in self.pending:
                    self.pending.pop(control)
                    self.emit(control, bindings["double"], "double")
                elif "double" in bindings:
                    self.pending[control] = (now + self.double, bindings.get("single", {"type": "none"}))
                else:
                    self.emit(control, bindings.get("single", {"type": "none"}), "single")

    def tick(self, now=None):
        now = self.clock() if now is None else now
        for control, state in list(self.down.items()):
            if not state["edge"] and not state["fired"] and "hold" in state["bindings"]:
                if now - state["time"] >= self.hold:
                    state["fired"] = True
                    self.pending.pop(control, None)
                    self.emit(control, state["bindings"]["hold"], "hold")
        for control, (deadline, action) in list(self.pending.items()):
            # A second press within the window reserves the pending click.
            if now >= deadline and control not in self.down:
                del self.pending[control]
                self.emit(control, action, "single")
