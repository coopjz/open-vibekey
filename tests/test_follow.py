import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vibekey.config import default_config, migrate, validate
from vibekey.follow import active_window, match_rule, window_info
from vibekey.runtime import Runtime
from vibekey.cli_terminal import launch
from vibekey.presets import presets


def rule(**fields):
    value = dict(id='codex', name='Codex CLI', wm_class='', title='', role='vibekey-codex', profile='codex-cli', layer=0)
    value.update(fields)
    return value


class FollowTests(unittest.TestCase):
    def config(self):
        value = default_config()
        value['profiles']['codex-cli'] = presets()['codex-cli']['profile']
        value['auto_follow'].update(enabled=True, rules=[rule()])
        return value

    def test_migration_preserves_existing_default_and_disables_following(self):
        value = default_config()
        del value['auto_follow']
        value['profiles']['custom'] = value['profiles'].pop('default')
        value['active_profile'] = 'custom'
        migrated = migrate(value)
        self.assertEqual(migrated['auto_follow']['default_profile'], 'custom')
        self.assertFalse(migrated['auto_follow']['enabled'])
        self.assertNotIn('auto_follow', value)

    def test_rule_matches_class_title_role_and_first_rule_wins(self):
        window = dict(id='0x1', wm_class='gnome-terminal-server.Gnome-terminal', title='CODEX CLI — 中文', role='vibekey-codex')
        specific = rule(wm_class='gnome-terminal', title='codex cli')
        self.assertEqual(match_rule(window, [specific, rule(id='second')]), specific)
        for fields in [dict(wm_class='terminal'), dict(title='claude'), dict(role='other')]:
            self.assertIsNone(match_rule(window, [rule(**fields)]))
        # Stable roles still match when the CLI changes its title.
        self.assertIsNotNone(match_rule(dict(window, title='A task name'), [rule()]))
        self.assertIsNone(match_rule(dict(window, role=''), [rule()]))

    def test_validation_rejects_catch_all_and_missing_profiles(self):
        for fields in [dict(role=''), dict(profile='missing'), dict(layer=True), dict(layer=4), dict(title='\0')]:
            value = self.config()
            value['auto_follow']['rules'] = [rule(**fields)]
            with self.assertRaises(ValueError):
                validate(value)
        value = self.config()
        value['auto_follow']['default_profile'] = 'missing'
        with self.assertRaises(ValueError):
            validate(value)
        value = self.config()
        value['auto_follow']['rules'].append(rule())
        with self.assertRaises(ValueError):
            validate(value)

    def test_xprop_unicode_properties_and_no_active_window(self):
        output = 'WM_CLASS(STRING) = "gnome-terminal-server", "Gnome-terminal"\n_NET_WM_NAME(UTF8_STRING) = "中文 \\"quoted\\""\nWM_WINDOW_ROLE(STRING) = "vibekey-codex"\n'
        with mock.patch('vibekey.follow._query', return_value=output):
            window = window_info('0x123')
        self.assertEqual(window['wm_class'], 'gnome-terminal-server.Gnome-terminal')
        self.assertEqual(window['title'], '中文 "quoted"')
        with mock.patch('vibekey.follow._query', return_value='_NET_ACTIVE_WINDOW(WINDOW): window id # 0x0'):
            self.assertEqual(active_window()['id'], '')
        with self.assertRaises(ValueError):
            window_info('bad;command')

    def test_follow_switch_return_default_and_release_held_without_disk_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            runtime = Runtime(path, simulate=True)
            try:
                value = self.config()
                runtime.save(value)
                before = path.read_bytes()
                runtime.backend.hold_shortcut('RIGHTALT', True, 'top')
                window = dict(id='0x1', wm_class='Gnome-terminal', title='Task', role='vibekey-codex')
                runtime.update_follow(window, value['auto_follow'])
                self.assertEqual(runtime.state()['active_profile'], 'codex-cli')
                self.assertFalse(runtime.backend.held)
                self.assertEqual(runtime.bindings('knob')['single']['keys'], 'CTRL+R')
                runtime.switch({'type': 'layer', 'index': 2})
                runtime.update_follow(dict(window, title='New task title'), value['auto_follow'])
                self.assertEqual(runtime.state()['active_layer'], 2)
                runtime.update_follow(dict(window, id='0x2', role=''), value['auto_follow'])
                self.assertEqual(runtime.state()['active_profile'], 'default')
                self.assertEqual(runtime.state()['active_layer'], 0)
                self.assertEqual(runtime.store.value['active_profile'], 'default')
                self.assertEqual(path.read_bytes(), before)
                runtime.update_follow(window, value['auto_follow'])
                runtime.update_follow(None, value['auto_follow'], available=False, error='probe failed')
                self.assertEqual(runtime.state()['active_profile'], 'default')
                value['auto_follow']['enabled'] = False
                runtime.update_follow(None, value['auto_follow'])
                self.assertIsNone(runtime.follow_selection)
            finally:
                runtime.close()

    def test_cli_presets_do_not_use_workbuddy_voice_or_exit_shortcut(self):
        for pid in ('codex-cli', 'claude-code'):
            bindings = presets()[pid]['profile']['layers'][0]['bindings']
            self.assertEqual(bindings['top']['single']['keys'], 'RIGHTALT')
            self.assertEqual(bindings['top']['single']['mode'], 'hold')
            self.assertEqual(bindings['bottom']['single']['keys'], 'ESC')
            self.assertEqual(bindings['middle']['single']['keys'], 'ENTER')
            self.assertEqual(bindings['ccw']['single']['keys'], 'UP')
            self.assertEqual(bindings['cw']['single']['keys'], 'DOWN')

    def test_cli_launcher_uses_fixed_role_and_argv(self):
        with mock.patch('vibekey.cli_terminal.executable', return_value='/path/codex'), mock.patch('vibekey.cli_terminal.shutil.which', return_value='/usr/bin/gnome-terminal'), mock.patch('vibekey.cli_terminal.subprocess.run') as popen:
            launch('codex', ['--resume'], '/tmp/project with spaces')
            argv = popen.call_args[0][0]
            self.assertIn('--role=vibekey-codex', argv)
            self.assertIn('--working-directory=/tmp/project with spaces', argv)
            self.assertEqual(argv[-3:], ['--', '/path/codex', '--resume'])
            self.assertNotIn('shell', popen.call_args[1])
        with self.assertRaises(ValueError):
            launch('unknown')
