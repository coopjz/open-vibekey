import http.client
import json
import queue
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from vibekey.config import default_config
from vibekey.events import EventBus
from vibekey.runtime import Runtime
from vibekey.server import Server


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(Path(self.temp.name) / "config.json", simulate=True)
        self.client = self.runtime.bus.subscribe()

    def tearDown(self):
        self.runtime.close()
        self.temp.cleanup()

    def test_preview_suppresses_execution(self):
        self.runtime.preview(15)
        self.runtime.control_event("knob", True)
        self.assertFalse(self.runtime.gestures.down)
        self.runtime.preview(0)
        self.runtime.control_event("knob", True)
        deadline = time.monotonic() + 1
        events = []
        while time.monotonic() < deadline:
            try:
                event = self.client.get(timeout=.1)
                events.append(event["type"])
                if "simulated_action" in events:
                    break
            except queue.Empty:
                pass
        self.assertIn("simulated_action", events)

    def test_momentary_layer_releases_original_binding(self):
        config = default_config()
        config["profiles"]["default"]["layers"][0]["bindings"]["top"] = {
            "single": {"type": "momentary_layer", "index": 2}}
        self.runtime.save(config)
        self.runtime.control_event("top", True)
        self.assertEqual(self.runtime.state()["active_layer"], 2)
        self.runtime.control_event("top", False)
        self.assertEqual(self.runtime.state()["active_layer"], 0)

    def test_cancel_clears_keys_pending_gestures_and_voice(self):
        self.runtime.backend.held.add(29)
        self.runtime.control_event("top", True)
        self.runtime.cancel()
        self.assertFalse(self.runtime.backend.held)
        self.assertFalse(self.runtime.gestures.down)
        self.assertEqual(self.runtime.voice.state, "idle")

    def test_failed_save_preserves_running_config(self):
        config = default_config()
        config["version"] = 100
        with self.assertRaises(ValueError):
            self.runtime.save(config)
        self.assertEqual(self.runtime.store.value["version"], 1)

    def test_simulation_never_executes_shell_or_text_helper(self):
        with mock.patch("vibekey.actions.subprocess.Popen") as popen, \
                mock.patch.object(self.runtime.helper, "send") as helper:
            self.runtime.runner.submit({"type": "shell", "value": "exit 1"})
            self.runtime.runner.submit({"type": "text", "value": "hello"})
            time.sleep(.1)
            popen.assert_not_called()
            helper.assert_not_called()

    def test_macro_cancellation(self):
        self.runtime.runner.submit({"type": "macro", "steps": [
            {"delay_ms": 1000}, {"type": "shell", "value": "never"}]})
        time.sleep(.03)
        self.runtime.runner.cancel()
        time.sleep(.05)
        events = []
        while not self.client.empty():
            events.append(self.client.get_nowait())
        self.assertFalse(any(event["type"] == "simulated_action" for event in events))

    def test_slow_subscriber_is_bounded(self):
        for i in range(300):
            self.runtime.bus.publish("test", value=i)
        self.assertEqual(self.client.qsize(), 128)


class APITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = Runtime(Path(self.temp.name) / "config.json", simulate=True)
        self.server = Server(self.runtime, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.runtime.close()
        self.temp.cleanup()

    def request(self, path, body=None, method="GET", headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        supplied = {"Host": "127.0.0.1:%d" % self.port}
        if body is not None:
            supplied["Content-Type"] = "application/json"
        supplied.update(headers or {})
        connection.request(method, path, json.dumps(body) if body is not None else None, supplied)
        response = connection.getresponse()
        status = response.status
        data = response.read()
        connection.close()
        return status, data

    def test_state_and_ui(self):
        status, raw = self.request("/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["token"], self.server.token)
        self.assertTrue(json.loads(raw)["simulate"])
        self.assertIn(b"VibeKey", self.request("/")[1])

    def test_host_origin_token(self):
        self.assertEqual(self.request("/api/state", headers={"Host":"evil.example"})[0], 403)
        self.assertEqual(self.request("/api/state", headers={"Origin":"https://evil.example"})[0], 403)
        self.assertEqual(self.request("/api/cancel", {}, "POST")[0], 403)
        self.assertEqual(self.request("/api/cancel", {}, "POST",
                                     {"X-VibeKey-Token":self.server.token})[0], 200)

    def test_save_export_import(self):
        config = default_config()
        config["active_layer"] = 2
        headers = {"X-VibeKey-Token":self.server.token}
        self.assertEqual(self.request("/api/config", config, "PUT", headers)[0], 200)
        self.assertEqual(json.loads(self.request("/api/config")[1])["active_layer"], 2)
        config["active_layer"] = 99
        self.assertEqual(self.request("/api/config", config, "PUT", headers)[0], 400)

    def test_preview_and_simulation(self):
        headers = {"X-VibeKey-Token":self.server.token}
        self.assertEqual(self.request("/api/preview", {"seconds":15}, "POST", headers)[0], 200)
        self.assertEqual(self.request("/api/simulate", {"control":"top","pressed":True}, "POST", headers)[0], 200)
        self.assertTrue(self.runtime.state()["preview"])
        self.assertFalse(self.runtime.gestures.down)
        self.assertEqual(self.request("/api/simulate", {"control":"top","pressed":"yes"}, "POST", headers)[0], 400)

    def test_sse_delivers_event(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request("GET", "/api/events")
        response = connection.getresponse()
        self.assertEqual(response.status, 200)
        self.assertEqual(response.fp.readline(), b"retry: 2000\n")
        response.fp.readline()
        self.runtime.bus.publish("test", value=42)
        self.assertTrue(response.fp.readline().startswith(b"id: "))
        self.assertIn(b'"value": 42', response.fp.readline())
        connection.close()

    def test_path_traversal(self):
        self.assertEqual(self.request("/../vibekey/config.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
