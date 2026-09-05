import unittest
from unittest.mock import patch

from trainer_relay import window_probe
from trainer_relay.window_probe import collect_window_snapshot


class WindowProbeTests(unittest.TestCase):
    def test_steam_game_write_uses_shell_free_xprop_boundary(self):
        environment = {'DISPLAY': ':1'}

        with patch('trainer_relay.window_probe._run_x11', return_value='') as run_x11:
            result = window_probe._set_x11_steam_game(environment, '0x20', 2476768691)

        self.assertTrue(result)
        run_x11.assert_called_once_with(
            'xprop',
            ['-id', '0x20', '-f', 'STEAM_GAME', '32c', '-set', 'STEAM_GAME', '2476768691'],
            environment,
            output_limit=256,
            timeout=.5,
        )

    def test_associates_only_owned_window_with_shortcut_appid_and_verifies_write(self):
        steam_game_id = str((2476768691 << 32) | 0x02000000)
        properties = {
            '0x20': iter((
                '_NET_WM_PID(CARDINAL) = 31304\n',
                '_NET_WM_PID(CARDINAL) = 31304\n',
                '_NET_WM_PID(CARDINAL) = 31304\nSTEAM_GAME(CARDINAL) = 2476768691\n',
            )),
            '0x21': iter(('_NET_WM_PID(CARDINAL) = 31186\n',)),
        }
        writes = []
        associate = getattr(
            window_probe,
            'associate_owned_windows',
            lambda *args, **kwargs: {'association_status': 'not_implemented'},
        )

        result = associate(
            {'DISPLAY': ':1'},
            999,
            steam_game_id,
            list_windows=lambda _: ('0x20', '0x21'),
            read_properties=lambda _, window: next(properties[window]),
            set_steam_game=lambda environment, window, appid: writes.append(
                (environment, window, appid)
            ) or True,
            get_process_group=lambda pid: {31304: 999, 31186: 777}[pid],
        )

        self.assertEqual(
            result,
            {
                'association_status': 'associated',
                'owned_window_count': 1,
                'associated_window_count': 1,
                'already_associated_count': 0,
                'failed_window_count': 0,
            },
        )
        self.assertEqual(writes, [({'DISPLAY': ':1'}, '0x20', 2476768691)])

    def test_never_writes_a_foreign_process_window(self):
        writes = []
        associate = getattr(
            window_probe,
            'associate_owned_windows',
            lambda *args, **kwargs: {'association_status': 'not_implemented'},
        )

        result = associate(
            {'DISPLAY': ':1'},
            999,
            str((2476768691 << 32) | 0x02000000),
            list_windows=lambda _: ('0x21',),
            read_properties=lambda *_: '_NET_WM_PID(CARDINAL) = 31186\n',
            set_steam_game=lambda *args: writes.append(args) or True,
            get_process_group=lambda _: 777,
        )

        self.assertEqual(result['association_status'], 'no_owned_windows')
        self.assertEqual(writes, [])

    def test_rejects_invalid_shortcut_identity_before_window_enumeration(self):
        enumerations = []
        associate = getattr(
            window_probe,
            'associate_owned_windows',
            lambda *args, **kwargs: {'association_status': 'not_implemented'},
        )

        result = associate(
            {'DISPLAY': ':1'},
            999,
            '2476768691',
            list_windows=lambda _: enumerations.append(True) or (),
        )

        self.assertEqual(result['association_status'], 'invalid_steam_game_id')
        self.assertEqual(enumerations, [])

    def test_does_not_rewrite_an_already_associated_owned_window(self):
        writes = []
        associate = getattr(
            window_probe,
            'associate_owned_windows',
            lambda *args, **kwargs: {'association_status': 'not_implemented'},
        )

        result = associate(
            {'DISPLAY': ':1'},
            999,
            str((2476768691 << 32) | 0x02000000),
            list_windows=lambda _: ('0x20',),
            read_properties=lambda *_: (
                '_NET_WM_PID(CARDINAL) = 31304\nSTEAM_GAME(CARDINAL) = 2476768691\n'
            ),
            set_steam_game=lambda *args: writes.append(args) or True,
            get_process_group=lambda _: 999,
        )

        self.assertEqual(result['association_status'], 'already_associated')
        self.assertEqual(result['already_associated_count'], 1)
        self.assertEqual(writes, [])

    def test_association_stops_enumerating_after_global_deadline(self):
        associated = '_NET_WM_PID(CARDINAL) = 31304\nSTEAM_GAME(CARDINAL) = 2476768691\n'
        associate = getattr(
            window_probe,
            'associate_owned_windows',
            lambda *args, **kwargs: {'association_status': 'not_implemented'},
        )

        with patch('trainer_relay.window_probe.time.monotonic', side_effect=(0.0, 0.1, 3.0)):
            result = associate(
                {'DISPLAY': ':1'},
                999,
                str((2476768691 << 32) | 0x02000000),
                list_windows=lambda _: ('0x20', '0x21'),
                read_properties=lambda *_: associated,
                get_process_group=lambda _: 999,
            )

        self.assertEqual(result['owned_window_count'], 1)
        self.assertEqual(result['association_status'], 'deadline_exceeded')

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
