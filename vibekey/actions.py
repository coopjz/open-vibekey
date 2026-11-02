import os
import queue
import signal
import subprocess
import threading
import time


def terminate(process):
    if process and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=1)
        except ProcessLookupError:
            pass
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


class ActionRunner:
    def __init__(self, backend, bus, text, switch, voice, simulate=False):
        self.backend, self.bus = backend, bus
        self.text, self.switch, self.voice = text, switch, voice
        self.simulate = simulate
        self.queue = queue.Queue(maxsize=64)
        self.guard = threading.RLock()
        self.cancel_event = threading.Event()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._run, name="actions", daemon=True)
        self.thread.start()

    def submit(self, action):
        with self.guard:
            try:
                self.queue.put_nowait((action, self.cancel_event))
            except queue.Full:
                self.bus.publish("error", message="Action queue full")

    def cancel(self):
        with self.guard:
            self.cancel_event.set()
            self.cancel_event = threading.Event()
            while True:
                try:
                    self.queue.get_nowait()
                except queue.Empty:
                    break
        self.backend.release_all()

    def close(self):
        self.stopping.set()
        self.cancel()
        self.thread.join(timeout=3)
        self.backend.close()

    def _run(self):
        while not self.stopping.is_set():
            try:
                action, cancelled = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._execute(action, cancelled)
            except Exception as exc:
                # Never log shell contents, text, API bodies or credentials.
                self.bus.publish("error", message="Action failed (%s)" % type(exc).__name__)

    def _process(self, argv, cancelled):
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 300
        try:
            while process.poll() is None:
                if cancelled.wait(0.05):
                    return
                if time.monotonic() > deadline:
                    raise TimeoutError("Action timed out")
            if process.returncode:
                raise RuntimeError("Process failed")
        finally:
            terminate(process)

    def _execute(self, action, cancelled):
        if cancelled.is_set():
            return
        kind = action["type"]
        if kind == "none":
            return
        if kind == "macro":
            for step in action.get("steps", []):
                if cancelled.is_set():
                    return
                if "delay_ms" in step:
                    cancelled.wait(step["delay_ms"] / 1000.0)
                else:
                    self._execute(step, cancelled)
        elif kind in ("layer", "profile"):
            self.switch(action)
        elif kind == "voice":
            self.voice(action["operation"])
        elif self.simulate:
            self.bus.publish("simulated_action", action=kind)
        elif kind == "shortcut":
            for _ in range(action.get("repeat", 1)):
                if cancelled.is_set():
                    break
                self.backend.shortcut(action["keys"], cancelled)
        elif kind == "volume":
            self.backend.shortcut({"up": "VOLUMEUP", "down": "VOLUMEDOWN", "mute": "MUTE"}[action["operation"]], cancelled)
        elif kind == "text":
            self.text(action.get("value", ""), True, cancelled)
        elif kind == "application":
            from .applications import focus_application
            if not focus_application(action.get("wm_class", "")):
                if cancelled.is_set():
                    return
                self._process(action["argv"], cancelled)
        elif kind == "shell":
            self._process(["/bin/sh", "-c", action.get("value", "")], cancelled)
