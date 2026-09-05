import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from trainer_relay import window_probe
from trainer_relay.process import ProcessDiscoverer, SessionIdentity
from trainer_relay.window_probe import collect_window_snapshot


class WindowProbeTests(unittest.TestCase):
    def test_default_process_verifier_reads_proc_before_mutating_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = root / '31304'
            process.mkdir()
            stat = '31304 (trainer.exe) S ' + ' '.join(['0'] * 18) + ' 9001 0 0'
            (process / 'stat').write_text(stat, encoding='utf-8')
            (process / 'cmdline').write_bytes(b'wine\0/games/trainers/mortal-shell.exe\0')
            (process / 'environ').write_bytes(b'WINEPREFIX=/prefixes/mortal-shell/pfx\0')
            properties = iter((
                '_NET_WM_PID(CARDINAL) = 31304\n',
                '_NET_WM_PID(CARDINAL) = 31304\n',
                '_NET_WM_PID(CARDINAL) = 31304\nSTEAM_GAME(CARDINAL) = 2476768691\n',
            ))
            writes = []

            with patch.object(
                window_probe,
                '_OWNED_PROCESS_DISCOVERER',
                ProcessDiscoverer(root),
            ):
                result = window_probe.associate_owned_windows(
                    {'DISPLAY': ':1'},
                    '/games/trainers/mortal-shell.exe',
                    '/prefixes/mortal-shell',
                    str((2476768691 << 32) | 0x02000000),
                    list_windows=lambda _: ('0x20',),
                    read_properties=lambda *_: next(properties),
                    set_steam_game=lambda *args: writes.append(args) or True,
                )

            self.assertEqual(result['association_status'], 'associated')
            self.assertEqual(len(writes), 1)

    def test_associates_service_launched_trainer_by_exact_process_identity_not_outer_group(self):
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

        def verify_process(pid, executable, prefix, expected_session=None):
            self.assertEqual(executable, '/games/trainers/mortal-shell.exe')
            self.assertEqual(prefix, '/prefixes/mortal-shell')
            if pid != 31304:
                return None
            session = SessionIdentity(31304, 9001)
            return session if expected_session in (None, session) else None

        result = window_probe.associate_owned_windows(
            {'DISPLAY': ':1'},
            '/games/trainers/mortal-shell.exe',
            '/prefixes/mortal-shell',
            steam_game_id,
            list_windows=lambda _: ('0x20', '0x21'),
            read_properties=lambda _, window: next(properties[window]),
            set_steam_game=lambda environment, window, appid: writes.append(
                (environment, window, appid)
            ) or True,
            verify_process=verify_process,
        )

        self.assertEqual(result['association_status'], 'associated')
        self.assertEqual(result['owned_window_count'], 1)
        self.assertEqual(writes, [({'DISPLAY': ':1'}, '0x20', 2476768691)])

    def test_fails_closed_before_writes_when_distinct_matching_trainer_processes_are_ambiguous(self):
        properties = {
            '0x20': iter((
                '_NET_WM_PID(CARDINAL) = 31304\n',
                '_NET_WM_PID(CARDINAL) = 31304\n',
                '_NET_WM_PID(CARDINAL) = 31304\nSTEAM_GAME(CARDINAL) = 2476768691\n',
            )),
            '0x22': iter((
                '_NET_WM_PID(CARDINAL) = 31400\n',
                '_NET_WM_PID(CARDINAL) = 31400\n',
                '_NET_WM_PID(CARDINAL) = 31400\nSTEAM_GAME(CARDINAL) = 2476768691\n',
            )),
        }
        writes = []

        result = window_probe.associate_owned_windows(
            {'DISPLAY': ':1'},
            '/games/trainers/mortal-shell.exe',
            '/prefixes/mortal-shell',
            str((2476768691 << 32) | 0x02000000),
            list_windows=lambda _: ('0x20', '0x22'),
            read_properties=lambda _, window: next(properties[window]),
            set_steam_game=lambda *args: writes.append(args) or True,
            verify_process=lambda pid, *_args: SessionIdentity(pid, pid + 100),
        )

        self.assertEqual(result['association_status'], 'ambiguous_owned_windows')
        self.assertEqual(result['owned_window_count'], 2)
        self.assertEqual(writes, [])

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
            '/games/trainers/mortal-shell.exe',
            '/prefixes/mortal-shell',
            steam_game_id,
            list_windows=lambda _: ('0x20', '0x21'),
            read_properties=lambda _, window: next(properties[window]),
            set_steam_game=lambda environment, window, appid: writes.append(
                (environment, window, appid)
            ) or True,
            verify_process=lambda pid, *_args: SessionIdentity(31304, 9001) if pid == 31304 else None,
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
            '/games/trainers/mortal-shell.exe',
            '/prefixes/mortal-shell',
            str((2476768691 << 32) | 0x02000000),
            list_windows=lambda _: ('0x21',),
            read_properties=lambda *_: '_NET_WM_PID(CARDINAL) = 31186\n',
            set_steam_game=lambda *args: writes.append(args) or True,
            verify_process=lambda *_args: None,
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
            '/games/trainers/mortal-shell.exe',
            '/prefixes/mortal-shell',
            '2476768691',
            list_windows=lambda _: enumerations.append(True) or (),
        )

        self.assertEqual(result['association_status'], 'invalid_steam_game_id')
        self.assertEqual(enumerations, [])

    def test_rejects_relative_trainer_or_prefix_before_window_enumeration(self):
        enumerations = []
        steam_game_id = str((2476768691 << 32) | 0x02000000)

        trainer_result = window_probe.associate_owned_windows(
            {'DISPLAY': ':1'},
            'trainer.exe',
            '/prefixes/mortal-shell',
            steam_game_id,
            list_windows=lambda _: enumerations.append(True) or (),
        )
        prefix_result = window_probe.associate_owned_windows(
            {'DISPLAY': ':1'},
            '/games/trainers/mortal-shell.exe',
            'relative-prefix',
            steam_game_id,
            list_windows=lambda _: enumerations.append(True) or (),
        )

        self.assertEqual(trainer_result['association_status'], 'invalid_trainer_path')
        self.assertEqual(prefix_result['association_status'], 'invalid_prefix')
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
            '/games/trainers/mortal-shell.exe',
            '/prefixes/mortal-shell',
            str((2476768691 << 32) | 0x02000000),
            list_windows=lambda _: ('0x20',),
            read_properties=lambda *_: (
                '_NET_WM_PID(CARDINAL) = 31304\nSTEAM_GAME(CARDINAL) = 2476768691\n'
            ),
            set_steam_game=lambda *args: writes.append(args) or True,
            verify_process=lambda *_args: SessionIdentity(31304, 9001),
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
                '/games/trainers/mortal-shell.exe',
                '/prefixes/mortal-shell',
                str((2476768691 << 32) | 0x02000000),
                list_windows=lambda _: ('0x20', '0x21'),
                read_properties=lambda *_: associated,
                verify_process=lambda *_args: SessionIdentity(31304, 9001),
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
