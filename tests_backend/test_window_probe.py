import unittest
from unittest.mock import patch

from trainer_relay.window_probe import collect_window_snapshot


class WindowProbeTests(unittest.TestCase):
    def test_non_ewmh_server_falls_back_to_tree_without_exporting_titles(self):
        from types import SimpleNamespace
        outputs = [
            '_NET_CLIENT_LIST:  no such atom on any window.\n',
            'xwininfo: Window id: 0x1 (the root window)\n  Root window id: 0x1\n'
            '  2 children:\n  0x20 "private title 0x999": ()  800x600+0+0\n'
            '  0x21 (has no name): ()  10x10+0+0\n',
            '_NET_WM_PID(CARDINAL) = 22711\n',
            'STEAM_GAME(CARDINAL) = 123\n',
        ]
        def respond(*args, **kwargs):
            kwargs['stdout'].write(outputs.pop(0).encode())
            return SimpleNamespace(returncode=0)
        with patch('trainer_relay.window_probe.shutil.which', side_effect=lambda name, **kw: '/usr/bin/' + name), patch(
            'trainer_relay.window_probe.subprocess.run', side_effect=respond
        ) as run:
            result = collect_window_snapshot({'DISPLAY': ':1'})
        self.assertEqual(result['probe_status'], 'ok_tree')
        self.assertEqual(result['window_count'], 2)
        self.assertIn('22711', result['window_properties'])
        self.assertNotIn('private', str(result))
        self.assertNotIn('0x999', str(result))
        self.assertEqual(run.call_args_list[1].args[0], ['/usr/bin/xwininfo', '-root', '-tree'])

    def test_missing_display_does_not_run_commands(self):
        with patch('trainer_relay.window_probe.subprocess.run') as run:
            self.assertEqual(collect_window_snapshot({})['probe_status'], 'missing_display')
            run.assert_not_called()

    def test_missing_tree_tool_reports_unavailable_not_zero_windows(self):
        from types import SimpleNamespace
        def respond(*args, **kwargs):
            kwargs['stdout'].write(b'_NET_CLIENT_LIST: no such atom\n')
            return SimpleNamespace(returncode=0)
        with patch('trainer_relay.window_probe.shutil.which', side_effect=['/usr/bin/xprop', None]), patch(
            'trainer_relay.window_probe.subprocess.run', side_effect=respond
        ):
            result = collect_window_snapshot({'DISPLAY': ':1'})
        self.assertEqual(result['probe_status'], 'xwininfo_unavailable')
        self.assertNotIn('window_count', result)

    def test_captures_numeric_properties_without_titles_or_private_environment(self):
        outputs = [
            '_NET_CLIENT_LIST(WINDOW): window id # 0x20\n_NET_ACTIVE_WINDOW(WINDOW): window id # 0x20',
            '_NET_WM_PID(CARDINAL) = 22711\nSTEAM_GAME(CARDINAL) = 123\nWM_STATE(WM_STATE):\n window state: Normal\n_NET_WM_NAME(UTF8_STRING) = "private title"',
        ]
        from types import SimpleNamespace
        def respond(*args, **kwargs):
            kwargs['stdout'].write(outputs.pop(0).encode())
            return SimpleNamespace(returncode=0)
        with patch('trainer_relay.window_probe.shutil.which', return_value='/usr/bin/xprop'), patch(
            'trainer_relay.window_probe.subprocess.run', side_effect=respond
        ) as run:
            result = collect_window_snapshot({'DISPLAY': ':1', 'SECRET': 'private'})
        self.assertEqual(result['probe_status'], 'ok')
        self.assertIn('22711', result['window_properties'])
        self.assertIn('Normal', result['window_properties'])
        self.assertNotIn('private', str(result))
        self.assertNotIn('SECRET', run.call_args.kwargs['env'])
        self.assertFalse(run.call_args.kwargs['shell'])

    def test_timeout_is_bounded_diagnostic(self):
        import subprocess
        with patch('trainer_relay.window_probe.shutil.which', return_value='/usr/bin/xprop'), patch(
            'trainer_relay.window_probe.subprocess.run', side_effect=subprocess.TimeoutExpired('xprop', .2)
        ):
            self.assertEqual(collect_window_snapshot({'DISPLAY': ':1'})['probe_status'], 'query_failed')

    def test_snapshot_survives_real_journal_export(self):
        import tempfile
        from pathlib import Path
        from trainer_relay.diagnostics import DiagnosticRecorder
        with tempfile.TemporaryDirectory() as directory:
            recorder = DiagnosticRecorder(Path(directory) / 'journal', enabled=True)
            recorder.record('trainer', 'window_snapshot', 'info', details={
                'probe_status': 'ok', 'display': ':1', 'window_count': 1,
                'truncated': False, 'active_window': '0x20',
                'window_properties': '0x20,_NET_WM_PID=22711,STEAM_GAME=123,state=Normal',
            })
            exported = recorder.export_text(Path(directory) / 'exports', 'test')
            text = Path(exported['path']).read_text()
            self.assertIn('window_snapshot', text)
            self.assertIn('22711', text)
