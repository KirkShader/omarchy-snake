"""Run explicitly: launching again with the same app ID refocuses the running game window."""
import subprocess
import sys
import time

from native_support import ROOT, NativeCheck, isolate_from_desktop_focus, until

from gi.repository import Gtk


def scenario(c, check):
    isolate_from_desktop_focus(c)
    yield 300
    second = subprocess.Popen(
        [sys.executable, str(ROOT / 'grid_preview.py')] + check.argv(),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    started = time.monotonic()
    try:
        yield until(lambda: second.poll() is not None, timeout_ms=8000, label='second launch exits')
    finally:
        if second.poll() is None:
            second.kill()
            second.wait()
    output = second.stdout.read()
    check.artifacts['second_launch'] = {'exit_code': second.returncode,
                                        'seconds': round(time.monotonic() - started, 2),
                                        'output': output[-500:]}
    assert second.returncode == 0, check.artifacts['second_launch']
    yield until(lambda: check.artifacts.get('reactivations') == 1, label='primary reactivated')
    application = c.window.get_application()
    assert len(application.get_windows()) == 1
    assert [w for w in Gtk.Window.list_toplevels() if w.get_visible()] == [c.window]
    check.ok('second_launch_refocuses_existing_window_without_a_new_one')


if __name__ == '__main__':
    raise SystemExit(NativeCheck('relaunch').run(scenario))
