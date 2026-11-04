"""Run explicitly: real GStreamer + PipeWire audio through the real GTK app. PLAYS SOUND.

Evidence comes from several places, because a pipeline can look healthy while silent or clipped:
- a pad probe on the real sink (what the volume element actually delivered),
- PipeWire's own node list (a stream exists and is running, or is gone),
- pw-record linked to the game's own stream, and a private recorder sink that receives a stream
  from its first sample (cues must arrive whole; silence and clipping both pass the other two).

Keyboard paths use GTK's own focus and key-binding signals; no OS-level keys are injected.
Uses its own application IDs and temporary settings/state; saved data is compared before and
after. If the backend is not pipewiresink, or the PipeWire tools are missing, it reports that
as a failure or a skip rather than claiming audio worked. Whether it sounds good is for the
player to judge.
"""
import array
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from native_support import (NativeCheck, choose_and_start, isolate_from_desktop_focus,
                            scratch_dir, screenshot, until)

from gi.repository import Gdk, GLib, Gtk

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from omarchy_snake import gst_audio, synth  # noqa: E402
from omarchy_snake.audio import NullBackend  # noqa: E402
from omarchy_snake.gst_audio import GstBackend, Gst  # noqa: E402
from omarchy_snake.log import GameLog  # noqa: E402
from omarchy_snake.preferences import default_dirs  # noqa: E402
from omarchy_snake.rules import MovementPreview  # noqa: E402

COLLISION = [(10, 10), (10, 11), (11, 11), (11, 10), (12, 10),
             (12, 11), (13, 11), (13, 10), (14, 10), (14, 11)]
FULL = synth.FULL_SCALE
MUSIC_PEAK_AT_30 = synth.MUSIC_PEAK * FULL * 0.3 * synth.MUSIC_GAIN
CUE_PEAK_AT_30 = synth.CUE_PEAK * FULL * 0.3


def factory():
    return MovementPreview(rng=random.Random(31), difficulty='Easy')


def press(c, name):
    return c.on_key(None, Gdk.keyval_from_name(name), 0, 0)


def state_of(channel):
    return channel.pipeline.get_state(Gst.SECOND)[1]


class SinkTap:
    """What really arrives at the sink element, after the volume element."""

    def __init__(self, channel):
        self.buffers = 0
        self.peak = 0
        self.first_at = None
        channel.sink.get_static_pad('sink').add_probe(Gst.PadProbeType.BUFFER, self._probe)

    def reset(self):
        self.buffers, self.peak, self.first_at = 0, 0, None

    def _probe(self, pad, info):
        buffer = info.get_buffer()
        data = array.array('h')
        data.frombytes(buffer.extract_dup(0, buffer.get_size() & ~1))
        self.buffers += 1
        peak = max((abs(v) for v in data), default=0)
        self.peak = max(self.peak, peak)
        if self.first_at is None and peak > 0:
            self.first_at = time.monotonic()  # Effects streams carry silence between cues.
        return Gst.PadProbeReturn.OK


def pipewire_tools():
    return all(shutil.which(tool) for tool in ('pw-record', 'pw-link', 'pw-dump'))


def our_nodes():
    """This process's game streams as PipeWire reports them: {channel: state}."""
    nodes = {}
    for item in json.loads(subprocess.check_output(['pw-dump'], timeout=5)):
        if 'Node' not in item.get('type', ''):
            continue
        name = item.get('info', {}).get('props', {}).get('node.name', '')
        for channel in ('sfx', 'music'):
            if name == f'omarchy-snake-{channel}-{os.getpid()}':
                nodes[channel] = item['info']['state']
    return nodes


class Capture:
    """Records one game stream from the PipeWire graph; removes its file when read."""
    rate = 48000

    def __init__(self, channel, seconds, as_sink=False):
        """as_sink makes a private sink a stream can target, so nothing else is recorded and
        nothing is audible. Otherwise link() taps the stream, which misses its first moments."""
        self.node = f'omarchy-snake-{channel}-{os.getpid()}'
        self.recorder = f'omarchy-snake-capture-{os.getpid()}-{time.monotonic_ns()}'
        self.path = scratch_dir() / f'{self.recorder}.raw'
        role = 'media.class=Audio/Sink' if as_sink else 'node.autoconnect=false'
        self.process = subprocess.Popen(
            ['timeout', '-k', '1', str(seconds), 'pw-record', '-P',
             '{ node.name=%s %s }' % (self.recorder, role),
             '--rate', str(self.rate), '--channels', '1', '--format', 's16', '--raw', str(self.path)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def link(self):
        """True once the game stream's port is linked into the recorder."""
        ports = subprocess.run(['pw-link', '-o'], capture_output=True, text=True, timeout=3).stdout
        port = next((line for line in ports.splitlines() if line.startswith(self.node + ':')), None)
        if port is None:
            return False
        inputs = subprocess.run(['pw-link', '-i'], capture_output=True, text=True, timeout=3).stdout
        target = next((line for line in inputs.splitlines() if line.startswith(self.recorder + ':')), None)
        if target is None:
            return False
        return subprocess.run(['pw-link', port, target], capture_output=True, timeout=3).returncode == 0

    def finished(self):
        return self.process.poll() is not None

    def read(self):
        data = array.array('h')
        raw = self.path.read_bytes() if self.path.exists() else b''
        data.frombytes(raw[:len(raw) & ~1])
        self.path.unlink(missing_ok=True)
        active = [i for i, v in enumerate(data) if abs(v) > 30]
        return {'samples': len(data), 'peak': max((abs(v) for v in data), default=0),
                'sounds_ms': self.sounds(active)}

    def sounds(self, active):
        """Length of each burst of sound, separated by more than 80 ms of silence."""
        lengths, start, last = [], None, None
        for index in active:
            if start is None:
                start = index
            elif index - last > self.rate * 0.08:
                lengths.append(round((last - start) * 1000 / self.rate))
                start = index
            last = index
        if start is not None:
            lengths.append(round((last - start) * 1000 / self.rate))
        return lengths


def capture_running_stream(channel, seconds, into):
    capture = Capture(channel, seconds)
    yield 200
    assert capture.link(), f'could not link {channel} into the recorder'
    yield until(capture.finished, int(seconds * 1000) + 3000, 'recorder finished')
    into.update(capture.read())


def saved_data_fingerprint():
    config, state = default_dirs()
    fingerprint = {}
    for path in (config / 'settings.json', state / 'scores.json'):
        fingerprint[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return fingerprint


def serpentine(cells):
    return [(x if y % 2 == 0 else cells - 1 - x, y) for y in range(cells) for x in range(cells)]


def ahead(game):
    return (game.snake[0][0] + 1, game.snake[0][1])


def arrange(c, **fields):
    """Set up the run's next step; callbacks run between ticks, so no step sees a partial state."""
    for name, value in fields.items():
        setattr(c.game, name, value)


def main_run(c, check):
    game, w, backend = c.game, c.widgets, c.audio.backend
    assert not isinstance(backend, NullBackend), 'the real backend failed to start'
    assert backend.sink_name == 'pipewiresink', f'expected pipewiresink, got {backend.sink_name}'
    check.artifacts['sink'] = backend.sink_name
    check.artifacts['gstreamer'] = Gst.version_string()
    isolate_from_desktop_focus(c)
    music, cues = backend.channels['music'], backend.channels['sfx']
    music_tap, cue_tap = SinkTap(music), SinkTap(cues)
    settings_path = check.config_dir / 'settings.json'

    def cue_done():
        return backend.cue_pcm is None and backend.cue_pending is None

    # Launch chooser: nothing plays, and previewing, Back and Esc-to-Back stay silent.
    yield 500
    assert w['difficulty-overlay'].get_visible() and c.audio.music_state == 'stopped'
    assert (music_tap.buffers, cue_tap.buffers) == (0, 0)
    assert our_nodes() == {}, our_nodes()
    w['difficulty-hard'].emit('clicked')
    w['difficulty-back'].emit('clicked')
    w['difficulty-normal'].emit('clicked')
    assert press(c, 'Escape') and w['difficulty-choices-page'].get_visible()
    yield 300
    assert (music_tap.buffers, cue_tap.buffers) == (0, 0)
    assert our_nodes() == {}
    check.ok('chooser_startup_preview_back_are_silent_with_no_stream')

    # Start: one cue through the real sink, then both channels as live PipeWire streams.
    started_at = time.monotonic()
    choose_and_start(c, 'Easy')
    assert cues.cue_bytes == len(synth.cue('start')), cues.cue_bytes
    yield until(lambda: cue_tap.peak > 0, label='start cue reached the sink')
    check.artifacts['start_cue_ms_to_first_sound_at_sink'] = round((cue_tap.first_at - started_at) * 1000, 1)
    yield until(lambda: music_tap.buffers > 3, label='music reached the sink')
    assert state_of(music) == Gst.State.PLAYING
    yield 500
    nodes = our_nodes()
    assert nodes == {'sfx': 'running', 'music': 'running'}, nodes
    check.artifacts['nodes_while_playing'] = nodes
    check.ok('start_plays_one_cue_and_both_channels_are_running_pipewire_streams')

    # Real samples leave the sink at the expected, modest level.
    yield until(cue_done, label='start cue done')
    assert CUE_PEAK_AT_30 * 0.9 <= cue_tap.peak <= CUE_PEAK_AT_30 * 1.1, cue_tap.peak
    captured = {}
    if pipewire_tools():
        yield from capture_running_stream('music', 2.2, captured)
        check.artifacts['music_capture'] = captured
        assert captured['samples'] > 0
        assert MUSIC_PEAK_AT_30 * 0.7 <= captured['peak'] <= MUSIC_PEAK_AT_30 * 1.2, captured
        check.ok('music_samples_captured_from_the_pipewire_graph_at_expected_level')
    else:
        check.ok('SKIPPED_graph_capture_pipewire_tools_missing')
    assert CUE_PEAK_AT_30 / (music_tap.peak or 1) > 2, (CUE_PEAK_AT_30, music_tap.peak)

    # Every pause reason closes both streams, keeps the melody's place; removing it continues.
    def freeze(label, enter, leave):
        yield until(lambda: music_tap.buffers > 0, label=f'music before {label}')
        enter()
        assert state_of(music) == Gst.State.READY and state_of(cues) == Gst.State.READY, label
        assert c.audio.music_state == 'paused', label
        position = backend.music_offset
        music_tap.reset()
        cue_tap.reset()
        yield 300
        assert (music_tap.buffers, cue_tap.buffers) == (0, 0), (label, music_tap.buffers, cue_tap.buffers)
        assert 'running' not in our_nodes().values(), (label, our_nodes())
        assert backend.music_offset == position, label
        leave()
        assert not c.session.paused, label
        yield until(lambda: music_tap.buffers > 0, label=f'music resumed after {label}')
        check.ok(f'pause_{label}_silences_both_and_resume_continues')

    yield from freeze('manual_escape', lambda: press(c, 'Escape'), lambda: press(c, 'Escape'))
    yield from freeze('focus', lambda: c.session.focus_changed(False), lambda: c.session.focus_changed(True))
    yield from freeze('color_dialog', lambda: c.on_color_dialog(True), lambda: c.on_color_dialog(False))
    yield from freeze('difficulty', c.open_new_game, c.cancel_difficulty)

    # Rewards through real movement: exactly the matching cue each time; no sound on plain steps.
    yield 300  # past the resumed stream's lead-in
    cue_tap.reset()
    ticks = game.ticks
    yield until(lambda: game.ticks >= ticks + 4, label='plain steps')
    assert cue_tap.peak == 0 and cue_tap.buffers > 0, (cue_tap.peak, cue_tap.buffers)
    check.ok('plain_steps_make_no_sound')

    arrange(c, foods={ahead(game)}, green_dot=None)
    score = game.score
    yield until(lambda: game.score == score + 1, label='orange collected')
    assert cues.cue_bytes == len(synth.cue('orange')), cues.cue_bytes
    yield until(lambda: cue_tap.peak >= CUE_PEAK_AT_30 * 0.9, label='orange reached the sink')
    assert cue_tap.peak <= CUE_PEAK_AT_30 * 1.1, cue_tap.peak
    check.ok('orange_collected_plays_the_orange_cue')

    yield until(cue_done, label='orange done')
    assert state_of(cues) == Gst.State.PLAYING, 'the stream stays open between cues'
    arrange(c, foods=set(), green_dot=ahead(game))
    length = len(game.snake)
    yield until(lambda: len(game.snake) == length - 2, label='green collected')
    assert cues.cue_bytes == len(synth.cue('green')), cues.cue_bytes
    check.ok('green_collected_plays_the_green_cue')

    # Options through the real widgets, as the keyboard bindings drive them.
    w['main-menu'].popup()
    yield until(lambda: w['main-popover'].get_visible(), label='menu open')
    assert c.audio.music_state == 'paused' and state_of(music) == Gst.State.READY
    w['menu-options'].emit('clicked')
    yield until(lambda: w['options-panel'].get_mapped(), label='options shown')
    yield 200  # tab order needs the panel laid out
    assert c.window.get_focus() is w['border-color'], c.window.get_focus()
    popover = w['main-popover']
    visited = []
    for _ in range(12):
        popover.child_focus(Gtk.DirectionType.TAB_FORWARD)
        focus = c.window.get_focus()
        visited.append(focus.get_name() if focus else None)
        if focus is w['options-back']:
            break
    for name in ('music-switch', 'sfx-switch', 'volume-scale', 'options-back'):
        assert name in visited, (name, visited)
    check.artifacts['options_tab_order'] = visited
    check.ok('options_controls_reachable_by_tab')
    yield 300
    check.artifacts['options_screenshot'] = screenshot('audio-options')

    # activate() is what Space/Enter do on a focused switch; GTK flips it after its animation.
    def press_switch(name, expected):
        w[name].grab_focus()
        assert w[name].activate()
        yield until(lambda: w[name].get_active() is expected, label=f'{name} toggled')

    yield from press_switch('music-switch', False)
    assert c.audio.music_state == 'stopped' and state_of(music) == Gst.State.READY
    saved = json.loads(settings_path.read_text())
    assert saved['music_enabled'] is False and saved['version'] == 1, saved
    yield from press_switch('sfx-switch', False)
    assert json.loads(settings_path.read_text())['sfx_enabled'] is False
    yield from press_switch('music-switch', True)
    yield from press_switch('sfx-switch', True)
    assert c.audio.music_state == 'stopped', 'enabling while paused must wait for resume'
    assert state_of(music) == Gst.State.READY and state_of(cues) == Gst.State.READY
    w['volume-scale'].grab_focus()
    before = w['volume-scale'].get_value()
    w['volume-scale'].emit('move-slider', Gtk.ScrollType.STEP_RIGHT)  # the Right-arrow binding
    assert w['volume-scale'].get_value() == before + 5, w['volume-scale'].get_value()
    assert c.audio.settings['master_volume'] == 0.35
    w['volume-scale'].emit('move-slider', Gtk.ScrollType.STEP_LEFT)
    assert c.audio.settings['master_volume'] == 0.30
    assert json.loads(settings_path.read_text())['master_volume'] == 0.30
    check.ok('switches_and_slider_work_through_keyboard_bindings_and_save_immediately')

    assert press(c, 'Escape') and not w['main-popover'].get_visible()  # Esc closes the menu
    assert not c.session.paused
    yield until(lambda: state_of(music) == Gst.State.PLAYING, label='music back on close')
    check.ok('closing_options_resumes_music_exactly_once')

    # Changes apply at once: double the volume, and the sink sees double the level.
    music_tap.reset()
    yield until(lambda: music_tap.peak > MUSIC_PEAK_AT_30 * 0.9, 8000, 'melody at 30%')
    low = music_tap.peak
    w['volume-scale'].set_value(60)
    yield 200
    music_tap.reset()
    yield until(lambda: music_tap.peak > MUSIC_PEAK_AT_30 * 1.5, 8000, 'melody at 60%')
    yield 500
    assert 1.6 <= music_tap.peak / low <= 2.3, (low, music_tap.peak)
    check.artifacts['music_peak_30_vs_60'] = [low, music_tap.peak]
    check.ok('volume_change_applies_immediately_at_the_sink')

    # Volume 0: no stream, no buffers, no cue, even across pause and resume.
    w['volume-scale'].set_value(0)
    assert c.audio.music_state == 'stopped' and state_of(music) == Gst.State.READY
    assert state_of(cues) == Gst.State.READY
    yield 300
    music_tap.reset()
    cue_tap.reset()
    arrange(c, foods={ahead(game)}, green_dot=None)
    score = game.score
    yield until(lambda: game.score == score + 1, label='orange at volume 0')
    press(c, 'Escape')
    press(c, 'Escape')
    yield 400
    assert (music_tap.buffers, cue_tap.buffers) == (0, 0), (music_tap.buffers, cue_tap.buffers)
    assert 'running' not in our_nodes().values(), our_nodes()
    check.ok('volume_zero_silences_both_and_stays_silent_through_pause_resume')

    # A channel left off is not resurrected by pause, resume or New Game.
    w['volume-scale'].set_value(30)
    assert c.audio.music_state == 'playing'
    w['music-switch'].set_active(False)
    assert c.audio.music_state == 'stopped'
    music_tap.reset()
    press(c, 'Escape')
    press(c, 'Escape')
    c.open_new_game()
    choose_and_start(c, 'Normal')
    assert cues.cue_bytes == len(synth.cue('start'))
    yield 500
    assert c.audio.music_state == 'stopped' and music_tap.buffers == 0
    check.ok('music_off_survives_pause_resume_and_new_game_while_effects_still_play')
    w['music-switch'].set_active(True)
    assert c.audio.music_state == 'playing'
    w['sfx-switch'].set_active(False)
    assert state_of(cues) == Gst.State.READY, 'switching effects off closes their stream'
    cue_tap.reset()
    arrange(c, foods={ahead(game)}, green_dot=None)
    score = game.score
    yield until(lambda: game.score == score + 1, label='orange with effects off')
    yield 200
    assert cue_tap.buffers == 0
    music_tap.reset()
    yield until(lambda: music_tap.buffers > 0, label='music continues with effects off')
    w['sfx-switch'].set_active(True)
    check.ok('effects_off_is_independent_of_music')

    # Loss: one low buzz, music stopped, nothing on later notifications or redraws.
    arrange(c, snake=list(COLLISION), direction='Right', queued_turns=[], foods=set(), green_dot=None)
    yield until(lambda: game.game_over, label='collision')
    assert cues.cue_bytes == len(synth.cue('game_over')), cues.cue_bytes
    assert c.audio.music_state == 'stopped' and state_of(music) == Gst.State.READY
    pending_cue = backend.cue_pending or backend.cue_pcm
    c.on_session('finished', c.session)
    assert (backend.cue_pending or backend.cue_pcm) is pending_cue, 'a repeated notification must not restart it'
    yield until(lambda: state_of(cues) == Gst.State.READY, 3000, 'buzz finished by itself')
    check.ok('collision_plays_game_over_once_and_stops_music')
    music_tap.reset()
    cue_tap.reset()
    w['game-over-new-game'].emit('clicked')
    w['difficulty-hard'].emit('clicked')
    w['difficulty-back'].emit('clicked')
    assert press(c, 'Escape')
    yield 300
    assert w['game-over-overlay'].get_visible()
    assert (music_tap.buffers, cue_tap.buffers) == (0, 0) and c.audio.music_state == 'stopped'
    check.ok('chooser_preview_and_cancel_after_a_loss_are_silent')

    # Orange and victory on one step: only the jingle, playing on after the run has stopped.
    w['game-over-new-game'].emit('clicked')
    choose_and_start(c, 'Hard')
    path = serpentine(32)
    c.session.pause('menu')
    arrange(c, snake=list(reversed(path[:-1])), direction='Left', queued_turns=[], foods={path[-1]},
            green_dot=None, score=1013)
    c.session.resume('menu')
    yield until(lambda: game.won, label='victory')
    assert cues.cue_bytes == len(synth.cue('victory')), cues.cue_bytes
    assert c.audio.music_state == 'stopped' and state_of(music) == Gst.State.READY
    assert state_of(cues) == Gst.State.PLAYING, 'the jingle plays on after the run has finished'
    yield until(lambda: state_of(cues) == Gst.State.READY, 4000, 'jingle ended by itself')
    check.ok('orange_with_victory_plays_only_the_jingle_to_its_end')

    # A long cue is cut by a pause reason and cannot leak into the next surface.
    w['victory-new-game'].emit('clicked')
    choose_and_start(c, 'Easy')
    yield until(lambda: music_tap.buffers > 0, label='music after victory')
    arrange(c, snake=list(COLLISION), direction='Right', queued_turns=[], foods=set(), green_dot=None)
    yield until(lambda: game.game_over, label='second collision')
    assert cues.cue_bytes == len(synth.cue('game_over')), 'finish cue works again in a new run'
    c.open_new_game()
    assert state_of(cues) == Gst.State.READY, 'opening the chooser cuts the buzz'
    choose_and_start(c, 'Easy')
    yield until(lambda: state_of(music) == Gst.State.PLAYING, label='music before closing')
    backend.play_cue('victory')  # the window now closes with both channels sounding
    check.ok('long_cue_cut_by_chooser_and_finish_cue_rearmed')


def after_main(c, check):
    backend = c.audio.backend
    for channel in backend.channels.values():
        assert state_of(channel) == Gst.State.NULL and not channel.watching
    backend.music('playing')
    backend.play_cue('victory')
    backend.hold_effects(True)
    for channel in backend.channels.values():
        assert state_of(channel) == Gst.State.NULL
    time.sleep(0.2)
    assert our_nodes() == {}, our_nodes()
    assert c.session.timer is None
    check.ok('close_released_pipelines_watches_and_streams_and_nothing_restarts')


def relaunch_run(c, check):
    """Settings written by the previous launch restore; music stays off because it was saved so."""
    w = c.widgets
    isolate_from_desktop_focus(c)
    yield 300
    assert c.audio.settings['music_enabled'] is False and not w['music-switch'].get_active()
    assert c.audio.settings['master_volume'] == 0.45 and w['volume-scale'].get_value() == 45
    assert c.audio.music_state == 'stopped'
    assert c.appearance['border_rgb'] == (10, 20, 30)
    check.ok('audio_settings_restored_and_colours_kept_on_next_launch')


def set_up_relaunch(shared):
    config = Path(shared.name) / 'config'
    config.mkdir(parents=True, exist_ok=True)
    (config / 'settings.json').write_text(json.dumps({
        'version': 1, 'border_rgb': [10, 20, 30], 'grid_rgb': [40, 50, 60], 'zoom': '100',
        'music_enabled': False, 'sfx_enabled': True, 'master_volume': 0.45}))


def silent_run(c, check):
    """No usable sink: the same game, silently, with every control still working."""
    game, w = c.game, c.widgets
    assert isinstance(c.audio.backend, NullBackend)
    isolate_from_desktop_focus(c)
    yield until(lambda: game.ticks >= 3, label='moves without audio')
    assert our_nodes() == {}
    arrange(c, foods={ahead(game)}, green_dot=None)
    score = game.score
    yield until(lambda: game.score == score + 1, label='scores without audio')
    w['music-switch'].set_active(False)
    w['volume-scale'].set_value(70)
    saved = json.loads((check.config_dir / 'settings.json').read_text())
    assert saved['music_enabled'] is False and saved['master_volume'] == 0.7
    press(c, 'Escape')
    press(c, 'Escape')
    arrange(c, snake=list(COLLISION), direction='Right', queued_turns=[], foods=set(), green_dot=None)
    yield until(lambda: game.game_over, label='finishes without audio')
    check.ok('no_sink_gives_silent_playable_game_with_working_options')


def cue_fidelity():
    """Every cue must arrive whole, from a cold stream and from a held one. The private sink
    receives the stream from its first sample; this stage is inaudible."""
    if not pipewire_tools():
        print(json.dumps({'cue_fidelity': 'SKIPPED: pw-record, pw-link or pw-dump missing'}), flush=True)
        return 0
    context = GLib.MainContext.default()

    def pump(seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            while context.iteration(False):
                pass
            time.sleep(0.002)

    def seconds(name):
        return len(synth.cue(name)) / synth.BYTES_PER_SAMPLE / synth.RATE

    backend = GstBackend(GameLog('quiet'))
    backend.set_levels(0.1, 0.3)
    capture = Capture('sfx', 10, as_sink=True)
    channel = backend.channels['sfx']
    time.sleep(0.4)
    channel.pipeline.set_state(Gst.State.NULL)
    channel.sink.set_property('target-object', capture.recorder)
    channel.stop()
    played = []

    def cue(name):
        played.append(name)
        backend.play_cue(name)

    for _ in range(3):  # Cold: each opens the stream, plays and closes.
        cue('orange')
        pump(1.0)
        assert state_of(channel) == Gst.State.READY, 'a cold cue should close its stream'
    backend.hold_effects(True)  # Held, as during play.
    pump(0.4)
    for name in ('orange', 'green', 'start', 'game_over', 'victory', 'orange', 'orange'):
        cue(name)
        pump(seconds(name) + 0.15)
    backend.hold_effects(False)
    cue('green')  # The finish path: released, and it must still play out whole.
    pump(1.0)
    assert state_of(channel) == Gst.State.READY, 'a released stream should close after its cue'
    backend.shutdown()
    while not capture.finished():
        time.sleep(0.05)
    heard = capture.read()
    expected = [round(seconds(name) * 1000) for name in played]
    close = (len(heard['sounds_ms']) == len(expected)
             and all(abs(a - b) <= 6 for a, b in zip(heard['sounds_ms'], expected)))
    print(json.dumps({'cue_fidelity': 'PASS' if close else 'FAIL', 'played': played, 'expected_ms': expected,
                      'captured_ms': heard['sounds_ms'], 'peak': heard['peak'],
                      'cue_peak_expected': round(CUE_PEAK_AT_30)}), flush=True)
    return 0 if close else 1


def main():
    before = saved_data_fingerprint()
    results = [NativeCheck('audio', ['--show-difficulty'], factory, global_timeout_ms=120000).run(main_run, after_main)]
    shared = tempfile.TemporaryDirectory(prefix='omarchy-snake-audio-')
    try:
        set_up_relaunch(shared)
        results.append(NativeCheck('audio_relaunch', ['--show-difficulty'], factory,
                                   shared_temp=shared).run(relaunch_run))
    finally:
        shared.cleanup()
    candidates = gst_audio.SINK_CANDIDATES
    gst_audio.SINK_CANDIDATES = ('no-such-sink',)
    try:
        results.append(NativeCheck('audio_silent', ['--verbose'], factory).run(silent_run))
    finally:
        gst_audio.SINK_CANDIDATES = candidates
    results.append(cue_fidelity())
    after = saved_data_fingerprint()
    print(json.dumps({'real_saved_data_unchanged': before == after, 'native_exit_codes': results}), flush=True)
    return max(results + [0 if before == after else 1])


if __name__ == '__main__':
    raise SystemExit(main())
