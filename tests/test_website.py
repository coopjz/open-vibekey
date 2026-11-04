import threading
import unittest
from unittest.mock import Mock

from vibekey.actions import ActionRunner
from vibekey.config import validate_action


class WebsiteTests(unittest.TestCase):
    def test_http_urls_and_macro(self):
        for url in ('https://example.com/a?q=one%20two#part', 'http://localhost:8080/', 'https://例子.测试/'):
            validate_action({'type': 'website', 'url': url})
            validate_action({'type': 'macro', 'steps': [{'type': 'website', 'url': url}]})

    def test_reject_invalid_or_non_web_targets(self):
        for url in (None, '', 'example.com', 'file:///etc/passwd', 'javascript:alert(1)',
                    'https:///path', 'https://host:bad/', 'https://host/a\nb',
                    'https://host/a b', 'https://host\\evil', '--help'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_action({'type': 'website', 'url': url})

    def test_dispatch_passes_url_as_single_argument_and_simulation_is_inert(self):
        runner = ActionRunner.__new__(ActionRunner)
        runner.simulate = False
        runner._process = Mock()
        runner.bus = Mock()
        action = {'type': 'website', 'url': 'https://example.com/?q=$(touch%20/tmp/no)&a=1'}
        cancelled = threading.Event()
        runner._execute(action, cancelled)
        runner._process.assert_called_once_with(['xdg-open', action['url']], cancelled)
        runner._process.reset_mock()
        runner.simulate = True
        runner._execute(action, cancelled)
        runner._process.assert_not_called()
        cancelled.set()
        runner.simulate = False
        runner._execute(action, cancelled)
        runner._process.assert_not_called()
