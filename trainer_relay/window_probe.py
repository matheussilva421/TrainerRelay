"""Bounded read-only X11 window metadata; never captures window titles."""

import re
import shutil
import subprocess
import tempfile
import time


def collect_window_snapshot(environment):
    display = environment.get('DISPLAY', '')
    if not re.fullmatch(r':[0-9]{1,5}(?:\.[0-9]{1,3})?', display):
        return {'probe_status': 'missing_display'}
    executable = shutil.which('xprop', path='/usr/bin:/bin')
    if not executable:
        return {'probe_status': 'xprop_unavailable'}
    env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'DISPLAY': display}
    if environment.get('XAUTHORITY'):
        env['XAUTHORITY'] = environment['XAUTHORITY']
    deadline = time.monotonic() + 2

    def query(args):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError()
        # Use a temporary output file so subprocess output cannot grow a Python pipe buffer.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                [executable, *args], env=env, shell=False, stdin=subprocess.DEVNULL,
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
        if clients is None:
            return {'probe_status': 'client_list_unavailable', 'display': display}
        ids = re.findall(r'0x[0-9a-fA-F]{1,16}\b', clients.group(0) if clients else '')
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
        return {'probe_status': 'ok', 'display': display, 'window_count': len(ids),
                'truncated': len(ids) > 8, 'active_window': active_ids[0] if active_ids else 'unknown',
                'window_properties': ';'.join(rows)}
    except (OSError, TimeoutError, subprocess.TimeoutExpired):
        return {'probe_status': 'query_failed', 'display': display}
