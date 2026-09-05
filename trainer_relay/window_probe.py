"""Bounded X11 metadata and guarded association for owned trainer windows."""

import ntpath
import posixpath
import re
import shutil
import subprocess
import tempfile
import time

from .process import ProcessDiscoverer


_X11_PATH = '/usr/bin:/bin'
_MAX_ASSOCIATION_WINDOWS = 64
_OWNED_PROCESS_DISCOVERER = ProcessDiscoverer()


def _safe_x11_environment(environment):
    display = environment.get('DISPLAY', '')
    if not re.fullmatch(r':[0-9]{1,5}(?:\.[0-9]{1,3})?', display):
        return None
    result = {'PATH': _X11_PATH, 'LC_ALL': 'C', 'DISPLAY': display}
    if environment.get('XAUTHORITY'):
        result['XAUTHORITY'] = environment['XAUTHORITY']
    return result


def _run_x11(tool, args, environment, *, output_limit=65536, timeout=.5):
    executable = shutil.which(tool, path=_X11_PATH)
    if not executable:
        raise OSError(f'{tool}_unavailable')
    env = _safe_x11_environment(environment)
    if env is None:
        raise ValueError('missing_display')
    with tempfile.TemporaryFile() as output:
        result = subprocess.run(
            [executable, *args], env=env, shell=False, stdin=subprocess.DEVNULL,
            stdout=output, stderr=subprocess.DEVNULL, timeout=timeout,
        )
        if result.returncode != 0:
            raise OSError(f'{tool}_failed')
        output.seek(0)
        return output.read(output_limit).decode('utf-8', 'replace')


def _list_x11_windows(environment, *, timeout=.5):
    tree = _run_x11('xwininfo', ['-root', '-tree'], environment, timeout=timeout)
    return tuple(dict.fromkeys(
        re.findall(r'^\s+(0x[0-9a-fA-F]{1,16})\s', tree, re.M)
    ))[:_MAX_ASSOCIATION_WINDOWS]


def _read_x11_window_properties(environment, window, *, timeout=.5):
    return _run_x11(
        'xprop', ['-id', window, '_NET_WM_PID', 'STEAM_GAME'], environment,
        output_limit=4096, timeout=timeout,
    )


def _set_x11_steam_game(environment, window, appid, *, timeout=.5):
    _run_x11(
        'xprop',
        ['-id', window, '-f', 'STEAM_GAME', '32c', '-set', 'STEAM_GAME', str(appid)],
        environment,
        output_limit=256,
        timeout=timeout,
    )
    return True


def _shortcut_appid(steam_game_id):
    if not isinstance(steam_game_id, str) or not steam_game_id.isascii():
        return None
    if not steam_game_id.isdecimal() or len(steam_game_id) > 20:
        return None
    value = int(steam_game_id)
    if value >= 1 << 64 or value & 0xffffffff != 0x02000000:
        return None
    appid = value >> 32
    return appid if 0x80000000 <= appid <= 0xffffffff else None


def _is_absolute_path(value):
    return isinstance(value, str) and bool(value) and (posixpath.isabs(value) or ntpath.isabs(value))


def _verify_process_identity(pid, expected_executable, expected_prefix, expected_session=None):
    return _OWNED_PROCESS_DISCOVERER.verify_executable_session(
        pid,
        expected_executable,
        expected_prefix,
        expected_session,
    )


def associate_owned_windows(
    environment,
    expected_executable,
    expected_prefix,
    steam_game_id,
    *,
    list_windows=_list_x11_windows,
    read_properties=_read_x11_window_properties,
    set_steam_game=_set_x11_steam_game,
    verify_process=_verify_process_identity,
):
    """Assign the validated shortcut app ID only to owned trainer windows."""

    appid = _shortcut_appid(steam_game_id)
    if appid is None:
        return {'association_status': 'invalid_steam_game_id'}
    if not _is_absolute_path(expected_executable):
        return {'association_status': 'invalid_trainer_path'}
    if not _is_absolute_path(expected_prefix):
        return {'association_status': 'invalid_prefix'}
    if _safe_x11_environment(environment) is None:
        return {'association_status': 'missing_display'}

    counts = {
        'owned_window_count': 0,
        'associated_window_count': 0,
        'already_associated_count': 0,
        'failed_window_count': 0,
    }
    deadline = time.monotonic() + 2.0

    def remaining_timeout():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        return min(.5, remaining)

    try:
        windows = (
            list_windows(environment, timeout=remaining_timeout())
            if list_windows is _list_x11_windows
            else list_windows(environment)
        )
    except (OSError, subprocess.SubprocessError, TimeoutError, ValueError):
        return {'association_status': 'query_failed', **counts}

    deadline_exceeded = False
    owned_windows = []
    for window in tuple(windows)[:_MAX_ASSOCIATION_WINDOWS]:
        if time.monotonic() >= deadline:
            deadline_exceeded = True
            break
        try:
            initial = (
                read_properties(environment, window, timeout=remaining_timeout())
                if read_properties is _read_x11_window_properties
                else read_properties(environment, window)
            )
            pid_match = re.search(r'^_NET_WM_PID\(CARDINAL\)\s*=\s*(\d{1,10})\s*$', initial, re.M)
            if not pid_match:
                continue
            pid = int(pid_match.group(1))
            session = verify_process(pid, expected_executable, expected_prefix)
            if session is None:
                continue
            counts['owned_window_count'] += 1
            owned_windows.append((window, pid, session, initial))
        except (OSError, ProcessLookupError, subprocess.SubprocessError, TimeoutError, ValueError):
            counts['failed_window_count'] += 1

    if deadline_exceeded:
        return {'association_status': 'deadline_exceeded', **counts}
    if len({session for _, _, session, _ in owned_windows}) > 1:
        return {'association_status': 'ambiguous_owned_windows', **counts}

    for window, pid, session, initial in owned_windows:
        if time.monotonic() >= deadline:
            deadline_exceeded = True
            break
        try:
            steam_game = re.search(r'^STEAM_GAME\(CARDINAL\)\s*=\s*(\d{1,10})\s*$', initial, re.M)
            if steam_game and int(steam_game.group(1)) == appid:
                counts['already_associated_count'] += 1
                continue

            confirmed = (
                read_properties(environment, window, timeout=remaining_timeout())
                if read_properties is _read_x11_window_properties
                else read_properties(environment, window)
            )
            confirmed_pid = re.search(
                r'^_NET_WM_PID\(CARDINAL\)\s*=\s*(\d{1,10})\s*$', confirmed, re.M
            )
            if not confirmed_pid or int(confirmed_pid.group(1)) != pid:
                counts['failed_window_count'] += 1
                continue
            if verify_process(pid, expected_executable, expected_prefix, session) != session:
                counts['failed_window_count'] += 1
                continue
            write_succeeded = (
                set_steam_game(environment, window, appid, timeout=remaining_timeout())
                if set_steam_game is _set_x11_steam_game
                else set_steam_game(environment, window, appid)
            )
            if not write_succeeded:
                counts['failed_window_count'] += 1
                continue

            verified = (
                read_properties(environment, window, timeout=remaining_timeout())
                if read_properties is _read_x11_window_properties
                else read_properties(environment, window)
            )
            verified_pid = re.search(
                r'^_NET_WM_PID\(CARDINAL\)\s*=\s*(\d{1,10})\s*$', verified, re.M
            )
            verified_game = re.search(
                r'^STEAM_GAME\(CARDINAL\)\s*=\s*(\d{1,10})\s*$', verified, re.M
            )
            if (
                not verified_pid
                or int(verified_pid.group(1)) != pid
                or verify_process(pid, expected_executable, expected_prefix, session) != session
                or not verified_game
                or int(verified_game.group(1)) != appid
            ):
                counts['failed_window_count'] += 1
                continue
            counts['associated_window_count'] += 1
        except (OSError, ProcessLookupError, subprocess.SubprocessError, TimeoutError, ValueError):
            counts['failed_window_count'] += 1

    if deadline_exceeded:
        status = 'deadline_exceeded'
    elif not counts['owned_window_count']:
        status = 'no_owned_windows'
    elif counts['failed_window_count']:
        status = 'partial' if counts['associated_window_count'] or counts['already_associated_count'] else 'association_failed'
    elif counts['associated_window_count']:
        status = 'associated'
    else:
        status = 'already_associated'
    return {'association_status': status, **counts}


def collect_window_snapshot(environment):
    display = environment.get('DISPLAY', '')
    if not re.fullmatch(r':[0-9]{1,5}(?:\.[0-9]{1,3})?', display):
        return {'probe_status': 'missing_display'}
    executable = shutil.which('xprop', path=_X11_PATH)
    if not executable:
        return {'probe_status': 'xprop_unavailable'}
    env = {'PATH': _X11_PATH, 'LC_ALL': 'C', 'DISPLAY': display}
    if environment.get('XAUTHORITY'):
        env['XAUTHORITY'] = environment['XAUTHORITY']
    deadline = time.monotonic() + 2

    def query(args, tool=executable):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        # Use a temporary output file so subprocess output cannot grow a Python pipe buffer.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                [tool, *args], env=env, shell=False, stdin=subprocess.DEVNULL,
                stdout=output, stderr=subprocess.DEVNULL, timeout=min(.25, remaining),
            )
            if result.returncode != 0:
                raise OSError()
            output.seek(0)
            return output.read(16384).decode('utf-8', 'replace')

    try:
        root = query(['-root', '_NET_CLIENT_LIST', '_NET_ACTIVE_WINDOW'])
        clients = re.search(r'^_NET_CLIENT_LIST\([^\n]*', root, re.M)
        active = re.search(r'^_NET_ACTIVE_WINDOW\([^\n]*', root, re.M)
        status = 'ok'
        tree_truncated = False
        if clients is None:
            tree_tool = shutil.which('xwininfo', path=_X11_PATH)
            if not tree_tool:
                return {'probe_status': 'xwininfo_unavailable', 'display': display}
            tree = query(['-root', '-tree'], tree_tool)
            # Only leading IDs of tree rows; never parse IDs embedded in titles.
            ids = list(dict.fromkeys(re.findall(r'^\s+(0x[0-9a-fA-F]{1,16})\s', tree, re.M)))
            tree_truncated = len(tree.encode('utf-8')) >= 16384
            status = 'ok_tree'
        else:
            ids = re.findall(r'0x[0-9a-fA-F]{1,16}\b', clients.group(0))
        active_ids = re.findall(r'0x[0-9a-fA-F]{1,16}\b', active.group(0) if active else '')
        rows = []
        for window in ids[:8]:
            raw = query(['-id', window, '_NET_WM_PID', 'STEAM_GAME', 'WM_STATE', '_NET_WM_STATE'])
            fields = [window]
            for name in ('_NET_WM_PID', 'STEAM_GAME'):
                value = re.search(r'^' + name + r'\(CARDINAL\)\s*=\s*(\d{1,20})\s*$', raw, re.M)
                if value:
                    fields.append(name + '=' + value.group(1))
            state = re.search(r'window state:\s*(Normal|Iconic|Withdrawn)\b', raw)
            if state:
                fields.append('state=' + state.group(1))
            if re.search(r'^_NET_WM_STATE\(ATOM\).*\b_NET_WM_STATE_HIDDEN\b', raw, re.M):
                fields.append('hidden=1')
            rows.append(','.join(fields))
        return {'probe_status': status, 'display': display, 'window_count': len(ids),
                'truncated': len(ids) > 8 or tree_truncated, 'active_window': active_ids[0] if active_ids else 'unknown',
                'window_properties': ';'.join(rows)}
    except (OSError, TimeoutError, subprocess.TimeoutExpired):
        return {'probe_status': 'query_failed', 'display': display}
