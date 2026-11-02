import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from vibekey.actions import ActionRunner
from vibekey.applications import applications, focus_application
from vibekey.config import default_config, validate
from vibekey.events import EventBus
from vibekey.runtime import Runtime
from vibekey.uinput import UInput


class WorkspaceTests(unittest.TestCase):
    def test_new_shortcut_and_library_validation(self):
        value = default_config()
        binding = value["profiles"]["default"]["layers"][0]["bindings"]["knob"]
        for bad in ({"mode": "invalid"}, {"repeat": 21}, {"repeat": True},
                    {"mode": "hold", "repeat": 2}):
            binding["single"] = dict(type="shortcut", keys="F24", **bad)
            with self.assertRaises(ValueError):
                validate(value)
        binding["single"] = {"type": "shortcut", "keys": "KPENTER", "mode": "hold"}
        validate(value)
        binding["double"] = {"type": "none"}
        with self.assertRaises(ValueError):
            validate(value)
        value = default_config()
        item = {"id": "test", "name": "Terminal",
                "action": {"type": "application", "argv": ["/usr/bin/true"]}}
        value["library"] = {"applications": [item], "macros": []}
        validate(value)
        value["library"]["applications"].append(copy.deepcopy(item))
        with self.assertRaises(ValueError):
            validate(value)

    def test_inherited_held_shortcut_releases_and_cancel_clears(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(Path(directory) / "config.json", simulate=True)
            try:
                value = default_config()
                layers = value["profiles"]["default"]["layers"]
                layers[0]["bindings"]["knob"] = {
                    "single": {"type": "shortcut", "keys": "CTRL+A", "mode": "hold"}}
                layers[1]["bindings"]["knob"] = {
                    "single": {"type": "inherit"}, "double": {"type": "shortcut", "keys": "B"}}
                value["active_layer"] = 1
                runtime.save(value)
                self.assertEqual(runtime.bindings("knob"), layers[0]["bindings"]["knob"])
                runtime.control_event("knob", True)
                self.assertEqual(runtime.backend.held, {29, 30})
                runtime.control_event("knob", False)
                self.assertFalse(runtime.backend.held)
                runtime.control_event("knob", True)
                runtime.cancel()
                self.assertFalse(runtime.backend.held)
                self.assertFalse(runtime.backend.hold_groups)
                self.assertFalse(runtime.gestures.down)
            finally:
                runtime.close()

    def test_explicit_none_blocks_inheritance(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(Path(directory) / "config.json", simulate=True)
            try:
                value = default_config()
                value["active_layer"] = 2
                layers = value["profiles"]["default"]["layers"]
                layers[1]["bindings"]["knob"]["single"] = {"type": "none"}
                layers[2]["bindings"]["knob"]["single"] = {"type": "inherit"}
                runtime.save(value)
                self.assertEqual(runtime.bindings("knob")["single"], {"type": "none"})
            finally:
                runtime.close()

    def test_repeat_obeys_cancellation(self):
        backend = mock.Mock()
        runner = ActionRunner(backend, EventBus(), mock.Mock(), mock.Mock(), mock.Mock())
        try:
            cancellation = threading.Event()
            runner._execute({"type": "shortcut", "keys": "F13", "repeat": 3}, cancellation)
            self.assertEqual(backend.shortcut.call_count, 3)
            backend.shortcut.reset_mock()
            backend.shortcut.side_effect = lambda *args: cancellation.set()
            runner._execute({"type": "shortcut", "keys": "F13", "repeat": 10}, cancellation)
            self.assertEqual(backend.shortcut.call_count, 1)
        finally:
            runner.close()

    def test_overlapping_held_modifiers_and_tap_preserve_ownership(self):
        backend = UInput()
        events = []

        def key(code, pressed):
            events.append((code, pressed))
            backend.held.add(code) if pressed else backend.held.discard(code)

        # Exercise ownership logic without opening an input device.
        with mock.patch.object(backend, "key", side_effect=key):
            backend.hold_shortcut("CTRL+A", True, "top")
            backend.hold_shortcut("CTRL+B", True, "middle")
            backend.shortcut("CTRL+C")
            self.assertIn(29, backend.held)
            backend.hold_shortcut("CTRL+A", False, "top")
            self.assertEqual(backend.held, {29, 48})
            backend.hold_shortcut("CTRL+B", False, "middle")
            self.assertFalse(backend.held)
            self.assertEqual(events.count((29, True)), 1)
            self.assertEqual(events.count((29, False)), 1)

    def test_application_discovery_quoting_hidden_and_field_codes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.desktop").write_text(
                '[Desktop Entry]\nType=Application\nName=Test\n'
                'Exec="/opt/My App/bin/app" --name %c %U %%\n')
            (root / "hidden.desktop").write_text(
                '[Desktop Entry]\nType=Application\nName=Hidden\nHidden=true\nExec=hidden\n')
            (root / "bad.desktop").write_text(
                '[Desktop Entry]\nType=Application\nName=Bad\nExec=bad --file=%f\n')
            result = applications([root])
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["argv"],
                             ["/opt/My App/bin/app", "--name", "Test", "%"])

    def test_application_focus_matches_window_class_without_executing_shell(self):
        with mock.patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}), \
                mock.patch("vibekey.applications.shutil.which", return_value="/usr/bin/wmctrl"), \
                mock.patch("vibekey.applications.subprocess.run") as run:
            run.side_effect = [
                mock.Mock(stdout="0x123 0 host resource.Org.gnome.Terminal Some title\n"),
                mock.Mock(returncode=0),
            ]
            self.assertTrue(focus_application("Org.gnome.Terminal"))
            self.assertEqual(run.call_args.args[0], ["wmctrl", "-ia", "0x123"])
            run.reset_mock()
            self.assertFalse(focus_application(""))
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
