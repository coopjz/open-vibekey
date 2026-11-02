import copy
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

from .actions import terminate


class Voice:
    def __init__(self, settings, bus, deliver):
        self.settings, self.bus, self.deliver = settings, bus, deliver
        self.lock = threading.RLock()
        self.state = "idle"
        self.result = ""
        self.error = None
        self.recorder = None
        self.process = None
        self.temporary = None
        self.record_file = None
        self.worker = None
        self.generation = 0

    def snapshot(self):
        with self.lock:
            return {"state": self.state, "text": self.result, "error": self.error}

    def _state(self, state, error=None):
        self.state, self.error = state, error
        self.bus.publish("voice", state=state, text=self.result, error=error)

    def start(self):
        with self.lock:
            # Cancellation retains the worker until it has deleted its audio.
            if self.worker and self.worker.is_alive():
                return
            self.cancel()
            settings = copy.deepcopy(self.settings())
            try:
                self.temporary = tempfile.TemporaryDirectory(prefix="vibekey-audio-")
                self.raw_path = Path(self.temporary.name) / "audio.raw"
                self.record_file = self.raw_path.open("wb")
                argv = ["parec", "--format=s16le", "--rate=16000", "--channels=1"]
                if settings["source"]:
                    argv.append("--device=" + settings["source"])
                self.recorder = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=self.record_file,
                                                 stderr=subprocess.DEVNULL, start_new_session=True)
                self.deadline = time.monotonic() + settings["max_seconds"]
                self.record_settings = settings
                self.result = ""
                self._state("recording")
            except (OSError, ValueError):
                self._cleanup_recording()
                self._state("error", "Cannot start parec; check microphone and PulseAudio/PipeWire")

    def tick(self):
        with self.lock:
            if self.state == "recording":
                if self.recorder.poll() is not None:
                    self._cleanup_recording()
                    self._state("error", "Microphone stream ended; check selected source")
                elif time.monotonic() >= self.deadline:
                    self.stop()

    def stop(self):
        with self.lock:
            if self.state != "recording":
                return
            terminate(self.recorder)
            self.recorder = None
            self.record_file.close()
            self.record_file = None
            temporary = self.temporary
            self.temporary = None
            raw_path = self.raw_path
            settings = self.record_settings
            self._state("transcribing")
            generation = self.generation
            self.worker = threading.Thread(target=self._transcribe,
                                           args=(temporary, raw_path, settings, generation),
                                           name="transcription", daemon=True)
            self.worker.start()

    def _transcribe(self, temporary, raw_path, settings, generation):
        process = None
        try:
            raw = raw_path.read_bytes()
            if len(raw) < 3200:
                raise ValueError("Recording is too short")
            wav_path = Path(temporary.name) / "audio.wav"
            with wave.open(str(wav_path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(raw[:len(raw) // 2 * 2])
            config_file = Path(temporary.name) / "backend.json"
            config_file.write_text(json.dumps(settings), encoding="utf-8")
            output_path = Path(temporary.name) / "result.txt"
            with output_path.open("wb") as output:
                with self.lock:
                    if generation != self.generation:
                        return
                    process = subprocess.Popen(
                        [sys.executable, "-m", "vibekey.transcribe_worker", str(wav_path), str(config_file)],
                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL, start_new_session=True,
                    )
                    self.process = process
                deadline = time.monotonic() + settings["timeout_seconds"]
                while process.poll() is None:
                    with self.lock:
                        if generation != self.generation:
                            return
                    if output_path.stat().st_size > 1048576:
                        raise ValueError("Transcription output too large")
                    if time.monotonic() > deadline:
                        raise TimeoutError("Transcription timed out")
                    time.sleep(0.05)
            if process.returncode:
                raise RuntimeError("Backend failed")
            if output_path.stat().st_size > 1048576:
                raise ValueError("Transcription output too large")
            result = output_path.read_text(encoding="utf-8").strip()
            if not result:
                raise ValueError("Transcription returned no text")
            with self.lock:
                if generation != self.generation:
                    return
                self.result = result
                self._state("ready")
                if settings["auto_insert"]:
                    self.confirm()
        except Exception:
            with self.lock:
                if generation == self.generation:
                    self._state("error", "Transcription failed; check backend executable, model, network and credentials")
        finally:
            terminate(process)
            temporary.cleanup()
            with self.lock:
                if self.process is process:
                    self.process = None

    def confirm(self):
        with self.lock:
            if self.state != "ready":
                return
            text = self.result
            try:
                self.deliver(text)
                self._state("delivered")
            except Exception:
                self._state("error", "Text helper unavailable; copy the result from the web interface")

    def _cleanup_recording(self):
        terminate(self.recorder)
        self.recorder = None
        if self.record_file:
            self.record_file.close()
            self.record_file = None
        if self.temporary:
            self.temporary.cleanup()
            self.temporary = None

    def cancel(self):
        with self.lock:
            self.generation += 1
            self._cleanup_recording()
            terminate(self.process)
            self.process = None
            self.result = ""
            self._state("idle")

    def close(self):
        self.cancel()
        if self.worker:
            self.worker.join(timeout=3)
