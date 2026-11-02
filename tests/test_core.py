import copy
import json
import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from vibekey.config import ConfigStore, default_config, migrate, validate
from vibekey.device import Device, discover
from vibekey.gestures import Gestures
from vibekey.protocol import StandardDecoder, decode_vendor, encode_vendor, tea_block, vendor_event
from vibekey.uinput import parse_shortcut


class ProtocolTests(unittest.TestCase):
    def test_known_vector(self):
        self.assertEqual(tea_block(bytes(8)).hex(), "3890c499a360aaad")
        self.assertEqual(tea_block(tea_block(bytes(8)), True), bytes(8))

    def test_truncated_transport(self):
        plain = bytes(range(64))
        report = encode_vendor(plain)
        self.assertEqual(len(report), 64)
        self.assertEqual(decode_vendor(report), plain[:56])
        self.assertIsNone(decode_vendor(report[:-1]))
        with self.assertRaises(ValueError):
            encode_vendor(bytes(65))

    def test_vendor_physical_identity_not_logical_action(self):
        event = vendor_event(encode_vendor(bytes([0x8b, 0x10, 0x99, 1, 4])))
        self.assertEqual(event["control"], "cw")
        self.assertTrue(event["pulse"])

    def test_battery_unknown(self):
        event = vendor_event(encode_vendor(b"\x81\x01\x02\x11\x10\x0e\xff\xff\0\0\x05"))
        self.assertEqual(event["millivolts"], 3600)
        self.assertIsNone(event["percent"])
        self.assertIsNone(event["charging"])

    def test_keyboard_rollover_and_release(self):
        decoder = StandardDecoder()
        report = b"\x03\0\0\x01\0\0\0\0\0"
        self.assertEqual(decoder.feed(report), [("keyboard:00:01", True, False)])
        self.assertEqual(decoder.feed(report), [])
        self.assertEqual(decoder.feed(bytes([3]) + bytes(8)), [("keyboard:00:01", False, False)])

    def test_multiple_reports_independent(self):
        decoder = StandardDecoder()
        decoder.feed(b"\x03\0\0\x28" + bytes(5))
        self.assertEqual(decoder.feed(b"\x01\x01\0"), [("consumer:0001", True, False)])
        self.assertEqual(len(decoder.reset()), 2)
        self.assertEqual(decoder.reset(), [])

    def test_chord_modifier_first_release_is_one_press(self):
        decoder = StandardDecoder()
        reports = [
            b"\x03\x08\0" + bytes(6),
            b"\x03\x08\0\x0b" + bytes(5),
            b"\x03\0\0\x0b" + bytes(5),
            b"\x03" + bytes(8),
        ]
        edges = [edge for report in reports for edge in decoder.feed(report)]
        self.assertEqual(edges, [
            ("keyboard:08:0b", True, False),
            ("keyboard:08:0b", False, False),
        ])

    def test_chord_key_first_release_and_next_plain_key(self):
        decoder = StandardDecoder()
        self.assertEqual(decoder.feed(b"\x03\x08\0\x0b" + bytes(5)),
                         [("keyboard:08:0b", True, False)])
        self.assertEqual(decoder.feed(b"\x03\x08\0" + bytes(6)),
                         [("keyboard:08:0b", False, False)])
        self.assertEqual(decoder.feed(b"\x03" + bytes(8)), [])
        self.assertEqual(decoder.feed(b"\x03\0\0\x0b" + bytes(5)),
                         [("keyboard:00:0b", True, False)])

    def test_chord_reset_and_changed_keys(self):
        decoder = StandardDecoder()
        decoder.feed(b"\x03\x08\0\x0b" + bytes(5))
        self.assertEqual(decoder.feed(b"\x03\x08\0\x28" + bytes(5)), [
            ("keyboard:08:0b", False, False),
            ("keyboard:08:28", True, False),
        ])
        self.assertEqual(decoder.reset(), [("keyboard:08:28", False, False)])
        self.assertEqual(decoder.feed(b"\x03\x08\0\x28" + bytes(5)),
                         [("keyboard:08:28", True, False)])

    def test_physical_au05_session_all_six_controls(self):
        fixture = json.loads((Path(__file__).parent / "fixtures" /
                              "au05-standard-session.json").read_text())
        decoder = StandardDecoder()
        counts = Counter()
        held = set()
        presses = []
        for report in fixture["reports"]:
            for signature, pressed, pulse in decoder.feed(bytes.fromhex(report)):
                # Every actual report must map; modifier setup and teardown
                # must not leak a second unmodified control into the session.
                control = fixture["mapping"][signature]
                if pressed:
                    counts[control] += 1
                    presses.append(control)
                    if not pulse:
                        self.assertNotIn(control, held)
                        held.add(control)
                else:
                    self.assertIn(control, held)
                    held.remove(control)
        self.assertEqual(dict(counts), fixture["expected_press_counts"])
        self.assertEqual(presses, ["top", "middle", "bottom", "knob"] +
                         ["cw"] * 4 + ["ccw"] * 5)
        self.assertFalse(held)
        self.assertEqual(decoder.reset(), [])

    def test_wheel_pulses(self):
        decoder = StandardDecoder()
        self.assertEqual(decoder.feed(b"\x02\0\0\0\xfe"),
                         [("wheel:-", True, True)] * 2)
        self.assertEqual(decoder.feed(b"\x03"), [])


class GestureTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.events = []
        self.g = Gestures(lambda *event: self.events.append(event), clock=lambda: self.now)
        self.single = {"type": "text", "value": "s"}
        self.double = {"type": "text", "value": "d"}
        self.hold = {"type": "text", "value": "h"}

    def edge(self, pressed, bindings):
        self.g.edge("top", pressed, bindings)

    def test_immediate_without_double_or_hold(self):
        self.edge(True, {"single": self.single})
        self.assertEqual(self.events[0][2], "single")
        self.edge(False, {})
        self.assertEqual(len(self.events), 1)

    def test_double(self):
        bindings = {"single": self.single, "double": self.double}
        self.edge(True, bindings)
        self.edge(False, bindings)
        self.now = .1
        self.edge(True, bindings)
        self.edge(False, bindings)
        self.assertEqual([event[2] for event in self.events], ["double"])
        self.now = 1
        self.g.tick()
        self.assertEqual(len(self.events), 1)

    def test_single_after_window(self):
        bindings = {"single": self.single, "double": self.double}
        self.edge(True, bindings)
        self.edge(False, bindings)
        self.now = .3
        self.g.tick()
        self.assertEqual(self.events[0][1], self.single)

    def test_second_held_press_can_be_double(self):
        bindings = {"single": self.single, "double": self.double}
        self.edge(True, bindings); self.edge(False, bindings)
        self.now = .1
        self.edge(True, bindings)
        self.now = 1
        self.g.tick()
        self.assertEqual(self.events, [])
        self.edge(False, bindings)
        self.assertEqual(self.events[0][2], "double")

    def test_long_press_consumes_pending_click(self):
        bindings = {"single": self.single, "double": self.double, "hold": self.hold}
        self.edge(True, bindings); self.edge(False, bindings)
        self.now = .1
        self.edge(True, bindings)
        self.now = .7
        self.g.tick()
        self.edge(False, bindings)
        self.assertEqual([event[2] for event in self.events], ["hold"])

    def test_release_uses_press_snapshot(self):
        self.edge(True, {"single": self.single, "hold": self.hold})
        self.edge(False, {"single": {"type": "none"}})
        self.assertEqual(self.events[0][1], self.single)

    def test_ptt_and_reset(self):
        self.edge(True, {"single": {"type": "voice", "operation": "ptt"}})
        self.now = 3
        self.g.tick()
        self.g.reset()
        self.assertEqual([event[2] for event in self.events], ["press", "release"])

    def test_rotation_pulse_never_held(self):
        self.g.edge("cw", True, {"single": self.single}, pulse=True)
        self.assertFalse(self.g.down)
        self.assertEqual(len(self.events), 1)


class ConfigTests(unittest.TestCase):
    def test_default(self):
        validate(default_config())
        self.assertEqual(parse_shortcut("Control+shift+a"), [29, 42, 30])
        with self.assertRaises(ValueError):
            parse_shortcut("CTRL+UNSUPPORTED")

    def test_atomic_save_and_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            store.save(default_config())
            changed = default_config()
            changed["active_layer"] = 2
            store.save(changed)
            self.assertEqual(json.loads(path.read_text())["active_layer"], 2)
            self.assertEqual(json.loads(Path(str(path) + ".bak").read_text())["active_layer"], 0)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_invalid_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text("[]")
            store = ConfigStore(path)
            self.assertIsNotNone(store.error)
            self.assertEqual(path.read_text(), "[]")

    def test_reject_unsafe_edge_and_nested_macro(self):
        for action in ({"type": "voice", "operation": "ptt"},
                       {"type": "momentary_layer", "index": 1},
                       {"type": "macro", "steps": [{"type": "macro", "steps": []}]}):
            config = default_config()
            config["profiles"]["default"]["layers"][0]["bindings"]["cw"]["single"] = action
            with self.assertRaises(ValueError):
                validate(config)

    def test_reject_credentials_and_bad_urls(self):
        for key, value in (("api_key", "secret"), ("api_url", "http://remote.example/transcribe"),
                           ("api_url", "https://key@example.com/transcribe"),
                           ("api_url", "https://example.com/?key=secret")):
            config = default_config()
            config["voice"][key] = value
            with self.assertRaises(ValueError):
                validate(config)

    def test_unknown_macro_profile(self):
        config = default_config()
        config["profiles"]["default"]["layers"][0]["bindings"]["middle"] = {
            "single": {"type": "macro", "steps": [{"type": "profile", "id": "missing"}]}}
        with self.assertRaises(ValueError):
            validate(config)

    def test_version_migration(self):
        config = default_config()
        config["version"] = 0
        del config["voice"]
        self.assertEqual(migrate(config)["voice"]["max_seconds"], 120)
        self.assertNotIn("voice", config)


class DeviceTests(unittest.TestCase):
    def candidate(self):
        return {"id": "3-9", "serial": "x", "hidraw": [
            {"path": "/dev/hidraw1", "interface": "02"},
            {"path": "/dev/hidraw2", "interface": "03"}],
            "events": ["/dev/input/event1", "/dev/input/event2"]}

    def test_grab_failure_rolls_back(self):
        dev = Device(lambda *a: None, lambda *a: None, lambda *a: None)
        def ioctl(fd, request, value):
            if fd == 13 and value == 1:
                raise OSError("busy")
        with mock.patch("vibekey.device.os.open", side_effect=[10,11,12,13]), \
                mock.patch("vibekey.device.fcntl.ioctl", side_effect=ioctl) as grab, \
                mock.patch("vibekey.device.os.close") as close:
            with self.assertRaises(OSError):
                dev.connect([self.candidate()], {})
            self.assertIsNone(dev.selected)
            self.assertEqual(close.call_count, 4)
            self.assertIn(mock.call(12, 0x40044590, 0), grab.call_args_list)

    def test_ambiguous_devices_refused(self):
        dev = Device(None, None, None)
        with self.assertRaises(OSError):
            dev.connect([self.candidate(), self.candidate()], {})

    def test_discovery_does_not_include_other_keyboard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            usb = root / "devices/usb/3-9"
            usb.mkdir(parents=True)
            (usb / "idVendor").write_text("fff1")
            (usb / "idProduct").write_text("00dd")
            (usb / "serial").write_text("test")
            interface = usb / "3-9:1.2"
            hid = interface / "hid/hidraw/hidraw8"
            event = interface / "hid/input/input9/event9"
            hid.mkdir(parents=True); event.mkdir(parents=True)
            (interface / "bInterfaceNumber").write_text("02")
            for category, name, target in (("hidraw","hidraw8",hid),("input","event9",event)):
                base = root / "class" / category
                base.mkdir(parents=True, exist_ok=True)
                (base / name).symlink_to(target)
            other = root / "devices/other/event10"
            other.mkdir(parents=True)
            (root / "class/input/event10").symlink_to(other)
            devices = discover(directory)
            self.assertEqual(devices[0]["events"], ["/dev/input/event9"])
            self.assertEqual(devices[0]["serial"], "test")


if __name__ == "__main__":
    unittest.main()
