import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import wave
from pathlib import Path
from unittest import mock

from vibekey.config import default_config
from vibekey.events import EventBus
from vibekey.transcribe_worker import transcribe
from vibekey.voice import Voice


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.config = default_config()["voice"]
        self.voice = Voice(lambda: self.config, EventBus(), lambda text: None)

    def tearDown(self):
        self.voice.close()

    def transcribe_raw(self, command):
        self.config["command"] = command
        temporary = tempfile.TemporaryDirectory()
        raw_path = Path(temporary.name) / "audio.raw"
        raw_path.write_bytes(bytes(6400))
        self.voice.state = "recording"
        self.voice.temporary = temporary
        self.voice.raw_path = raw_path
        self.voice.record_settings = self.config.copy()
        self.voice.record_file = raw_path.open("ab")
        self.voice.stop()
        return temporary.name

    def test_external_command_wav_and_cleanup(self):
        code = ("import sys,wave; w=wave.open(sys.argv[1]); "
                "assert (w.getnchannels(),w.getframerate(),w.getsampwidth())==(1,16000,2); "
                "print('你好 VibeKey')")
        directory = self.transcribe_raw([sys.executable, "-c", code, "{audio}"])
        self.voice.worker.join(timeout=3)
        self.assertEqual(self.voice.state, "ready")
        self.assertEqual(self.voice.result, "你好 VibeKey")
        self.assertFalse(Path(directory).exists())

    def test_failed_backend_removes_audio(self):
        directory = self.transcribe_raw(["/nonexistent/vibekey-transcriber", "{audio}"])
        self.voice.worker.join(timeout=3)
        self.assertEqual(self.voice.state, "error")
        self.assertFalse(Path(directory).exists())

    def test_cancellation_kills_worker_and_deletes_audio(self):
        directory = self.transcribe_raw([sys.executable, "-c", "import time;time.sleep(10)", "{audio}"])
        deadline = time.monotonic() + 2
        while self.voice.process is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.voice.cancel()
        self.voice.worker.join(timeout=3)
        self.assertEqual(self.voice.state, "idle")
        self.assertFalse(Path(directory).exists())

    def test_timeout(self):
        self.config["timeout_seconds"] = 1
        directory = self.transcribe_raw([sys.executable, "-c", "import time;time.sleep(10)", "{audio}"])
        self.voice.worker.join(timeout=4)
        self.assertEqual(self.voice.state, "error")
        self.assertFalse(Path(directory).exists())

    def test_missing_recorder_is_visible(self):
        with mock.patch("vibekey.voice.subprocess.Popen", side_effect=FileNotFoundError):
            self.voice.start()
        self.assertEqual(self.voice.state, "error")
        self.assertIsNone(self.voice.temporary)

    def test_whisper_missing_model(self):
        config = dict(self.config, backend="whisper", model_path="/nonexistent/model")
        with self.assertRaises(ValueError):
            transcribe("/nonexistent/audio", config)

    def test_api_missing_secret(self):
        config = dict(self.config, backend="api", api_key_env="VIBEKEY_TEST_MISSING_KEY")
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            transcribe("/nonexistent/audio", config)

    def test_api_multipart_and_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "audio.wav"
            audio.write_bytes(b"RIFF-test")
            config = dict(self.config, backend="api", language="zh")
            opener = mock.MagicMock()
            opener.open.return_value.__enter__.return_value.read.return_value = json.dumps({"text":"测试"}).encode()
            with mock.patch.dict(os.environ, {"VIBEKEY_API_KEY":"secret"}), \
                    mock.patch("urllib.request.build_opener", return_value=opener):
                result = transcribe(str(audio), config)
            self.assertEqual(result, "测试")
            request = opener.open.call_args[0][0]
            self.assertEqual(request.get_header("Authorization"), "Bearer secret")
            self.assertIn(b"RIFF-test", request.data)
            self.assertIn(b'name="language"', request.data)


if __name__ == "__main__":
    unittest.main()
