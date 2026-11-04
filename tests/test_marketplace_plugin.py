"""Marketplace launcher: packaging contract, and the real QML under an isolated offscreen Quickshell.

Runtime tests copy the plugin to a scratch path full of awkward characters, beside a stub
grid_preview.py that only records its argv. The real Quickshell.execDetached therefore runs the
real /usr/bin/python without any game starting, and the plugin needs no test-only hook.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import textwrap
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ID = 'io.github.kirkshader.omarchy-snake'
PLUGIN_FILES = ('manifest.json', 'BarWidget.qml', 'omarchy-snake.svg', 'LICENSE')
ICON_SHA256 = '525787a5791533a29c0b8c4c2b8ab1d51f3a98d2f4122c33b748207533926a2c'
TOOLTIP = 'Omarchy Snake — play'
QS = shutil.which('qs', path='/usr/bin')
VALIDATOR = Path('/usr/share/omarchy/bin/omarchy-plugin-validate')
HOSTILE_DIR = 'Omarchy "Snake\'s" ünï 蛇 🐍 100%20 #1 ?x back\\slash $(touch INJECTED); touch INJECTED #'
STUB_GAME = textwrap.dedent('''\
    import json
    import sys
    from pathlib import Path
    with (Path(__file__).parent / 'launches.jsonl').open('a', encoding='utf-8') as record:
        record.write(json.dumps(sys.orig_argv) + '\\n')
''')


def scratch_parent():
    """Below $OMARCHY_SNAKE_SCRATCH when set, else the temp dir; resolved so paths compare exactly."""
    configured = os.environ.get('OMARCHY_SNAKE_SCRATCH')
    if configured:
        Path(configured).mkdir(parents=True, exist_ok=True)
        return Path(configured).resolve()
    return Path(tempfile.gettempdir()).resolve()


def relocated_plugin(base):
    plugin = base / 'relocated checkout' / HOSTILE_DIR
    plugin.mkdir(parents=True)
    for name in PLUGIN_FILES:
        shutil.copy(ROOT / name, plugin / name)
    (plugin / 'grid_preview.py').write_text(STUB_GAME, encoding='utf-8')
    return plugin


class PackagingTests(unittest.TestCase):
    def manifest(self):
        return json.loads((ROOT / 'manifest.json').read_text(encoding='utf-8'))

    def test_manifest_declares_the_approved_launcher(self):
        manifest = self.manifest()
        self.assertEqual(manifest['schemaVersion'], 1)
        self.assertEqual(manifest['id'], PLUGIN_ID)
        self.assertEqual(manifest['name'], 'Omarchy Snake')
        self.assertEqual(manifest['author'], 'Martin Kirwin (KirkShader)')
        self.assertEqual(manifest['license'], 'MIT')
        self.assertEqual(manifest['kinds'], ['bar-widget'])
        self.assertEqual(manifest['entryPoints'], {'barWidget': 'BarWidget.qml'})
        self.assertEqual(manifest['barWidget'], {
            'displayName': 'Omarchy Snake',
            'category': 'Games',
            'allowMultiple': False,
            'defaultSection': 'center',
        })
        self.assertIn('GTK', manifest['description'])
        self.assertNotIn('keepLoaded', manifest)

    def test_version_stays_the_literal_project_version(self):
        text = (ROOT / 'manifest.json').read_text(encoding='utf-8')
        self.assertRegex(text, r'"version":\s*"0\.0001"')
        self.assertEqual(self.manifest()['version'], (ROOT / 'VERSION').read_text(encoding='utf-8').strip())

    def test_icon_is_the_owners_original_with_no_external_references(self):
        icon = (ROOT / 'omarchy-snake.svg').read_bytes()
        self.assertEqual(hashlib.sha256(icon).hexdigest(), ICON_SHA256)
        self.assertNotRegex(icon.decode('utf-8'), r'href|<image|url\(')

    def test_widget_source_has_no_shell_or_user_specific_launch_path(self):
        source = (ROOT / 'BarWidget.qml').read_text(encoding='utf-8')
        self.assertRegex(source, r'(?m)^import QtQuick$')
        self.assertRegex(source, r'(?m)^import Quickshell$')
        self.assertNotRegex(source, r'bar\.run|shellQuote|\bsh\b|\bbash\b|/home/|\bProcess\s*\{|eval\(')

    @unittest.skipUnless(VALIDATOR.is_file(), 'Omarchy plugin validator is not installed')
    def test_installed_validator_accepts_the_repository_and_a_relocated_copy(self):
        with tempfile.TemporaryDirectory(dir=scratch_parent()) as base:
            for folder in (ROOT, relocated_plugin(Path(base))):
                with self.subTest(folder=str(folder)):
                    done = subprocess.run([str(VALIDATOR), str(folder)], capture_output=True, text=True, timeout=30)
                    self.assertEqual(done.returncode, 0, done.stderr)


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.readme = (ROOT / 'README.md').read_text(encoding='utf-8')

    def test_readme_gives_the_plugin_lifecycle_commands(self):
        for command in (
                'omarchy plugin add https://github.com/KirkShader/omarchy-snake.git --enable',
                f'omarchy plugin remove {PLUGIN_ID}',
                f'omarchy plugin disable {PLUGIN_ID}',
                f'omarchy bar move {PLUGIN_ID} --section',
                '/usr/bin/python grid_preview.py --show-difficulty',
                'sudo pacman -S --needed python python-gobject python-cairo gtk4',
                'gst-plugin-pipewire'):
            with self.subTest(command=command):
                self.assertIn(command, self.readme)

    def test_readme_describes_the_launcher_and_its_limits(self):
        self.assertIn('bar launcher', self.readme)
        self.assertRegex(self.readme, r'(?i)duplicate')
        self.assertRegex(self.readme, r'(?i)never installs? (any )?dependenc')
        self.assertNotRegex(self.readme, r'rm\s+[^\n]*\.(config|local)')

    def test_readme_no_longer_says_there_is_no_plugin(self):
        self.assertNotIn('not an Omarchy Hub package', self.readme)
        self.assertNotIn('It does **not** install a launcher/icon', self.readme)

    def test_approval_and_changelog_record_the_prerequisite(self):
        self.assertIn('marketplace launcher prerequisite', (ROOT / 'APPROVALS.md').read_text(encoding='utf-8').lower())
        changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
        unreleased = changelog.split('## 0.0001')[0]
        self.assertIn('bar launcher', unreleased)


@unittest.skipUnless(QS, 'Quickshell is not installed')
class LauncherRuntimeTests(unittest.TestCase):
    """Each test drives the unmodified BarWidget.qml through one action in its own qs process."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=scratch_parent())
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.plugin = relocated_plugin(self.base)

    def run_harness(self, action, screenshot=None):
        harness_dir = self.base / 'harness'
        harness_dir.mkdir(exist_ok=True)
        shutil.copy(ROOT / 'tests' / 'qml_launcher_harness.qml', harness_dir / 'shell.qml')
        home = self.base / 'home'
        runtime = self.base / 'runtime'
        work = self.base / 'cwd'
        for path in (home, runtime, work):
            path.mkdir(mode=0o700, exist_ok=True)
        # Built from nothing, so no Wayland, Hyprland, D-Bus or shell socket is reachable.
        env = {
            'PATH': '/usr/bin',
            'HOME': str(home),
            'XDG_CONFIG_HOME': str(home / 'config'),
            'XDG_STATE_HOME': str(home / 'state'),
            'XDG_CACHE_HOME': str(home / 'cache'),
            'XDG_DATA_HOME': str(home / 'data'),
            'XDG_RUNTIME_DIR': str(runtime),
            'TMPDIR': str(self.base),
            'QT_QPA_PLATFORM': 'offscreen',
            'QT_QUICK_BACKEND': 'software',
            'LANG': 'C.UTF-8',
            'HARNESS_PLUGIN_DIR': str(self.plugin),
            'HARNESS_ACTION': action,
        }
        if screenshot:
            env['HARNESS_SCREENSHOT'] = str(screenshot)
        process = subprocess.Popen(
            [QS, '--no-color', '-p', str(harness_dir / 'shell.qml')], cwd=work, env=env, text=True,
            encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            log, _ = process.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            log, _ = process.communicate()
            self.fail(f'harness timed out:\n{log}')
        match = re.search(r'HARNESS_RESULT (\{.*\})', log)
        self.assertIsNotNone(match, f'no harness result (exit {process.returncode}):\n{log}')
        result = json.loads(match.group(1))
        self.assertNotIn('loadError', result, log)
        self.assertNotRegex(log, r'(?m)^.*BarWidget\.qml.*$', 'the widget logged a QML warning or error')
        self.assertEqual(process.returncode, 0, log)
        return result

    def launches(self, expected):
        """The launches the stub recorded, waiting briefly because the process is detached."""
        record = self.plugin / 'launches.jsonl'
        deadline = time.monotonic() + (5 if expected else 0.3)
        while time.monotonic() < deadline:
            if expected and record.exists() and len(record.read_text(encoding='utf-8').splitlines()) >= expected:
                break
            time.sleep(0.05)
        if not record.exists():
            return []
        return [json.loads(line) for line in record.read_text(encoding='utf-8').splitlines()]

    def assert_launched_once(self):
        self.assertEqual(self.launches(1), [[
            '/usr/bin/python', str(self.plugin / 'grid_preview.py'), '--show-difficulty']])
        self.assertEqual(sorted(p.name for p in self.base.rglob('INJECTED*')), [])

    def test_loading_starts_nothing_and_renders_the_icon_in_its_target(self):
        result = self.run_harness('idle')
        self.assertEqual(self.launches(0), [])
        self.assertEqual(result['barRuns'], [])
        self.assertEqual((result['width'], result['height']), (28, 26))
        self.assertTrue(result['iconStatusReady'])
        self.assertEqual((result['iconWidth'], result['iconHeight']), (16, 16))

    def test_left_click_through_the_bars_slot_pointer_launches_exactly_once(self):
        result = self.run_harness('click-slot')
        self.assert_launched_once()
        self.assertEqual(result['barRuns'], [])
        self.assertGreaterEqual(result['tooltipHides'], 1)

    def test_left_click_without_a_slot_pointer_launches_exactly_once(self):
        self.run_harness('click-direct')
        self.assert_launched_once()

    def test_click_works_before_the_bar_is_injected(self):
        self.run_harness('click-no-bar')
        self.assert_launched_once()

    def test_right_click_does_not_launch(self):
        self.run_harness('click-right')
        self.assertEqual(self.launches(0), [])

    def test_host_forwarding_another_button_does_not_launch(self):
        self.run_harness('press-right')
        self.assertEqual(self.launches(0), [])

    def test_return_enter_and_space_launch_exactly_once_with_a_focus_indicator(self):
        for action in ('key-return', 'key-enter', 'key-space'):
            with self.subTest(action=action):
                record = self.plugin / 'launches.jsonl'
                record.unlink(missing_ok=True)
                result = self.run_harness(action)
                self.assert_launched_once()
                self.assertTrue(result['focusOnTab'])
                self.assertTrue(result['activeFocus'])
                self.assertFalse(result['indicatorBeforeFocus'])
                self.assertTrue(result['indicatorWithFocus'])

    def test_other_keys_do_not_launch(self):
        self.run_harness('key-x')
        self.assertEqual(self.launches(0), [])

    def test_hover_requests_the_bars_tooltip_and_leaving_hides_it(self):
        result = self.run_harness('hover')
        self.assertEqual(result['tooltips'], [{'text': TOOLTIP, 'hovered': True}])
        self.assertTrue(result['hoveredWhileInside'])
        self.assertFalse(result['hoveredAfterLeaving'])
        self.assertGreaterEqual(result['tooltipHides'], 1)
        self.assertEqual(self.launches(0), [])


if __name__ == '__main__':
    unittest.main()
