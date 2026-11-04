import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vibekey.config import default_config, validate, validate_action
from vibekey.device import Device
from vibekey.presets import presets
from vibekey.protocol import encode_vendor, vendor_event, lighting_commands, STATUS_QUERIES
from vibekey.runtime import Runtime
from vibekey.uinput import UInput


class PresetHardwareTests(unittest.TestCase):
    def test_presets_validate_without_replacing_active_profile(self):
        config = default_config()
        original = copy.deepcopy(config['profiles']['default'])
        for pid, item in presets().items():
            config['profiles'][pid] = item['profile']
        validate(config)
        self.assertEqual(config['active_profile'], 'default')
        self.assertEqual(config['profiles']['default'], original)
        bindings = config['profiles']['workbuddy-default']['layers'][0]['bindings']
        self.assertEqual(bindings['cw']['single'], {'type': 'scroll', 'direction': 'down'})
        self.assertEqual(bindings['ccw']['single']['direction'], 'up')
        self.assertEqual(config['profiles']['workbuddy-dispatch']['layers'][0]['bindings']['knob']['single']['keys'], 'CTRL+N')
        self.assertEqual(config['profiles']['workbuddy-multitask']['layers'][0]['bindings']['knob']['single']['keys'], 'SHIFT+ALT+W')
        catalog = presets()
        catalog['workbuddy-default']['profile']['name'] = 'changed'
        self.assertEqual(presets()['workbuddy-default']['profile']['name'], '默认预设')

    def test_lighting_command_fields_and_reply(self):
        commands = lighting_commands(2, 7)
        self.assertEqual(commands[0].hex(), '010b8804010002')
        self.assertEqual(commands[1].hex(), '010b880402000007')
        self.assertEqual(commands[2], STATUS_QUERIES[2])
        event = vendor_event(encode_vendor(bytes.fromhex('810b881100000107020a02070702')))
        self.assertEqual(event, {'kind': 'lighting', 'mode': 1, 'brightness': 7})
        self.assertIsNone(vendor_event(encode_vendor(bytes.fromhex('810b8814010001'))))
        for mode, brightness in [(True, 7), (3, 7), (1, True), (1, -1), (1, 21), (1, 2.5)]:
            with self.assertRaises(ValueError):
                lighting_commands(mode, brightness)

    def test_vendor_commands_never_use_keyboard_channel(self):
        device = Device(mock.Mock(), mock.Mock(), mock.Mock())
        device.raw = {9: '02', 10: '03'}
        device.selected = {'id': 'test'}
        device.next_status = float('inf')
        device.queue_commands([STATUS_QUERIES[1]])
        with mock.patch('vibekey.device.select.select', return_value=([], [], [])), mock.patch('vibekey.device.os.write', return_value=64) as write:
            device.poll()
            write.assert_called_once_with(10, encode_vendor(STATUS_QUERIES[1]))
        self.assertFalse(device.commands)

    def test_scroll_is_relative_wheel_event(self):
        backend = UInput()
        with mock.patch.object(backend, 'open'), mock.patch.object(backend, '_event') as event:
            backend.scroll('down')
            self.assertEqual(event.call_args_list, [mock.call(2, 8, -1), mock.call(0, 0, 0)])
        for value in ['left', None, 1]:
            with self.assertRaises(ValueError):
                validate_action({'type': 'scroll', 'direction': value})

    def test_lighting_needs_real_online_device_and_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Runtime(Path(directory) / 'config.json', simulate=True)
            try:
                with self.assertRaises(ValueError):
                    runtime.set_lighting(1, 7)
                runtime.simulate = False
                runtime.device.selected = {'id': 'test'}
                runtime.status.update(online=True, lighting={'mode': 1, 'brightness': 7})
                runtime.set_lighting(2, 10)
                self.assertEqual(runtime.status['light_operation']['state'], 'pending')
                with self.assertRaises(ValueError):
                    runtime.set_lighting(1, 7)
                runtime.device_status({'kind': 'lighting', 'mode': 1, 'brightness': 7})
                self.assertEqual(runtime.status['light_operation']['state'], 'pending')
                runtime.device_status({'kind': 'lighting', 'mode': 2, 'brightness': 10})
                self.assertEqual(runtime.status['light_operation']['state'], 'confirmed')
                runtime.device_status({'kind': 'online', 'online': False})
                self.assertIsNone(runtime.status['lighting'])
                self.assertIsNone(runtime.status['battery'])
            finally:
                runtime.close()
