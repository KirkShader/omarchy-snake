# Test log — approved audio slice (2026-11-04)

Genuine command output, trimmed to the relevant lines. Commands run from the repo root with system Python; `TMPDIR` was inherited from the session and resolved to `/home/bignutta/.hermes/cache/scratch`. Native screenshots went to `/home/bignutta/.hermes/cache/scratch/snake-audio-checks/`.

Baseline before any change:
```
$ /usr/bin/python -m unittest discover -s tests -q
Ran 139 tests in 0.139s
OK
```

## Runtime probe

GStreamer 1.28.8. Present: appsrc, volume, audioconvert, audioresample, pipewiresink, alsasink, audiomixer, audiotestsrc, capsfilter, fakesink, queue. Absent: pulsesink, autoaudiosink, wavparse. gst-python's overrides are also absent (`Gst.Bin.add()` takes one element).

## Slice 1 — synthesis

RED (minimal first test):
```
ImportError: cannot import name 'synth' from 'omarchy_snake'
Ran 1 test in 0.000s
FAILED (errors=1)
```
GREEN: `Ran 1 test in 0.000s / OK`. RED (remaining cues, bounds, envelopes, music):
```
KeyError: 'green'
AttributeError: module 'omarchy_snake.synth' has no attribute 'render_cue'
AttributeError: module 'omarchy_snake.synth' has no attribute 'music_loop'
Ran 8 tests in 0.002s
FAILED (errors=9)
```
GREEN: `Ran 8 tests in 0.095s / OK`. Measured: all cues and the loop render in 33.8 ms; largest cue 41,454 bytes; loop 269,892 bytes (6.12 s).

## Slice 2 — rules report the last reward

RED:
```
AttributeError: 'MovementPreview' object has no attribute 'last_reward'
Ran 6 tests in 0.009s
FAILED (errors=6)
```
GREEN: `Ran 6 tests in 0.010s / OK`.

## Slice 3 — preferences

RED:
```
ImportError: cannot import name 'DEFAULT_AUDIO' from 'omarchy_snake.preferences'
FAILED (errors=1)
```
GREEN, with the unchanged older preference tests: `Ran 20 tests in 0.031s / OK`.

## Slice 4 — AudioDirector

RED: import failure, `Ran 1 test / FAILED (errors=1)`. First implementation:
```
FAIL: test_cancelling_the_launch_chooser_plays_music_without_a_start_cue
AssertionError: Lists differ: ['stop_cues', 'music:playing'] != ['music:playing']
FAIL: test_volume_zero_silences_both_and_raising_it_restores_only_what_is_on
AssertionError: Lists differ: ['stop_cues'] != []
Ran 25 tests in 0.032s
FAILED (failures=2)
```
Both were my new tests over-specifying a harmless, idempotent `stop_cues`; those expectations were corrected. GREEN with the session tests: `Ran 53 tests in 0.054s / OK`.

## Slice 5 — GstBackend against fakesink

With the module missing the tests only skipped (`OK (skipped=15)`), which proves nothing, so a stub gave a true RED:
```
NotImplementedError
Ran 15 tests in 0.002s
FAILED (errors=15)
```
First implementation exposed the missing overrides:
```
TypeError: Gst.Bin.add() takes exactly 2 arguments (6 given)
Ran 15 tests in 0.034s
FAILED (errors=13)
```
GREEN: `Ran 15 tests in 1.327s / OK`.

## Slice 6 — window wiring and Options

RED:
```
AttributeError: 'SnakeWindow' object has no attribute 'options_back'
AttributeError: 'SnakeWindow' object has no attribute 'on_audio_switch'
AttributeError: 'SnakeWindow' object has no attribute 'on_volume_changed'
AssertionError: Lists differ: [] != ['shutdown']
AssertionError: Lists differ: [] != ['orange']
AssertionError: Expected 'grab_focus' to be called once. Called 0 times.
AssertionError: 0.3 != 0.8
Ran 9 tests in 0.022s
FAILED (failures=6, errors=3)
```
GREEN, whole suite: `Ran 211 tests in 1.618s / OK`.

Two changes to pre-existing test code, neither relaxing an assertion: the `controller()` helper in `tests/test_app_controller.py` now gives its window a silent `AudioDirector`, and `MonitorRefitTests` patches `GLib.timeout_add`, because `test_gst_audio` runs the default main context, which otherwise fired a timer queued for a widget-less window (a printed traceback, not a failure).

## What the real backend found

fakesink and mocks passed all of the following defects. Each was found by measuring real PipeWire output.

**1. One large buffer plays as silence.** Reaches EOS normally; stream linked to `pw-record`:
```
big    ports [...output_FL, ...output_FR] links [0, 0] samples 143360 peak 0
chunks ports [...output_FL, ...output_FR] links [0, 0] samples 141312 peak 1196
```
(Expected peak 1200.) Fix: small chunks.

**2. Stream properties were ignored.** `AssertionError: {}` from `our_nodes()`: pipewiresink creates its stream on the way to READY, and the name was set afterwards. Fix: name it before opening.

**3. EOS comes about 100 ms early, and stopping then cut the cue.** Timed from the real EOS message:
```
orange expected 80 eos 48    green expected 220 eos 117    start expected 230 eos 128
game_over expected 850 eos 748    victory expected 940 eos 839
```
A padding test went RED (`AssertionError: 0.0 not greater than or equal to 0.2`), then GREEN.

**4. Opening a stream swallows the start of a cue.** Even with padding, one stream per cue, through a private recorder sink that receives the stream from its first sample:
```
captured [33, 174, 184, 405, 399, 492, 363, 17]
expected [80, 220, 230, 850, 940, 80, 80]
```
A continuous stream spike gave `[80, 220, 230, 850, 940, 80, 80, 80, 80]`, exact. Fix: hold the effects stream open during active play, with a silent lead-in on cold starts. Tests RED first:
```
AttributeError: 'GstBackend' object has no attribute 'hold_effects'
AttributeError: module 'omarchy_snake.gst_audio' has no attribute 'LEAD_IN_CHUNKS'
AssertionError: <State.PAUSED: 3> != <State.READY: 2>
Ran 46 tests in 1.614s
FAILED (failures=2, errors=8)
```
GREEN: `Ran 55 tests in 4.300s / OK`.

**5. Re-opened streams stuttered.** `cue_fidelity` RED:
```
"cue_fidelity": "FAIL"
"expected_ms": [80, 80, 80, 80, 220, 230, 850, 940, 80, 80, 220]
"captured_ms": [80, 29, 30, 26, 54, 80, 220, 230, 850, 940, 80, 80, 181]
```
Fix: `stop()` goes through NULL, not just READY, closing the stream entirely. The same run stopped PipeWire's `'impl->recurse > 0' failed at loop.c:663 loop_unlock()` message, seen earlier on PAUSED/PLAYING transitions. GREEN below.

Measured main-thread cost after the fix (8 rounds, min/median/max): open 0.09/0.17/0.25 ms, stop 0.45/0.59/2.23 ms, cue on a held stream 0.0/0.01/0.53 ms. Handing a cue to a held stream until it reaches the sink: 0.92/22.91/23.15 ms. PipeWire's own queue then adds to that, inferred at around 100 ms from defect 3 and not measured end to end.

With PipeWire unreachable (`PIPEWIRE_REMOTE=no-such-remote`, sinks limited to pipewiresink):
```
NullBackend {"event": "audio_unavailable", "reason": "no usable audio sink (pipewiresink: cannot connect)"}
```

## Final results

Production code did not change after these native runs.

```
$ /usr/bin/python -m unittest discover -s tests -q
Ran 218 tests in 4.574s
OK
```
218 = the 139 baseline tests plus 79 new. Native checks, run one at a time with `-W ignore`, real audio on:

`tests/native_audio_check.py` (exit codes `[0, 0, 0, 0]`; 22 + 1 + 1 checks, 0 failures, 0 windows left):
```
chooser_startup_preview_back_are_silent_with_no_stream
start_plays_one_cue_and_both_channels_are_running_pipewire_streams
music_samples_captured_from_the_pipewire_graph_at_expected_level
pause_manual_escape_silences_both_and_resume_continues
pause_focus_silences_both_and_resume_continues
pause_color_dialog_silences_both_and_resume_continues
pause_difficulty_silences_both_and_resume_continues
plain_steps_make_no_sound
orange_collected_plays_the_orange_cue
green_collected_plays_the_green_cue
options_controls_reachable_by_tab
switches_and_slider_work_through_keyboard_bindings_and_save_immediately
closing_options_resumes_music_exactly_once
volume_change_applies_immediately_at_the_sink
volume_zero_silences_both_and_stays_silent_through_pause_resume
music_off_survives_pause_resume_and_new_game_while_effects_still_play
effects_off_is_independent_of_music
collision_plays_game_over_once_and_stops_music
chooser_preview_and_cancel_after_a_loss_are_silent
orange_with_victory_plays_only_the_jingle_to_its_end
long_cue_cut_by_chooser_and_finish_cue_rearmed
close_released_pipelines_watches_and_streams_and_nothing_restarts
audio_settings_restored_and_colours_kept_on_next_launch
no_sink_gives_silent_playable_game_with_working_options
{"cue_fidelity": "PASS", "played": ["orange", "orange", "orange", "orange", "green", "start", "game_over", "victory", "orange", "orange", "green"], "expected_ms": [80, 80, 80, 80, 220, 230, 850, 940, 80, 80, 220], "captured_ms": [80, 80, 80, 80, 220, 230, 850, 940, 80, 80, 220], "peak": 7505, "cue_peak_expected": 5898}
{"real_saved_data_unchanged": true, "native_exit_codes": [0, 0, 0, 0]}
```
Sink `pipewiresink`, GStreamer 1.28.8. Nodes while playing `{"sfx": "running", "music": "running"}`. Music from the graph: peak 1717 (expected 1720), one unbroken 1963 ms of sound in a 2.2 s capture. Start cue reached the sink in 128.9 ms (the lead-in). Music peak at 30% vs 60%: 1704 vs 3440. Cue peak 7505 is about 27% above the 5898 nominal level in the resampled recording; the sink-side peak was asserted within ±10% of nominal, and I attribute the excess to resampling overshoot on square waves, which is not proven.

Older checks, unmodified for this slice, all 0 failures and 0 windows left:

| Check | Checks passed |
| --- | --- |
| `native_chooser_check.py` | 9 |
| `native_pause_check.py` | 16 |
| `native_ui_check.py` | 13 + 1 |
| `native_game_over_check.py` | 5 |
| `native_hard_check.py` | 6 (floor cadence mean 50.1 ms, min 50.0, max 50.2) |
| `native_fit_check.py` | 4 + 1 + 2 + 5 |
| `native_relaunch_check.py` | 1 |

`native_pause_check` reported `focus_returned_to_game: false` and `main_window_inactive_while_dialog_open` all false as artifacts, which depend on desktop focus.

## Limitations

- Nobody has listened to this. Measurements cover presence, level, length and lifecycle, not whether it sounds good or whether the volume is comfortable.
- Keyboard: Tab order, switch `activate()` and the slider's `move-slider` binding were driven through GTK; no OS-level keys were sent. An attempt to send compositor keys with `hyprctl dispatch sendshortcut` failed with a syntax error and direct use was refused at the permission prompt, so it was removed.
- Focus pause was driven through `session.focus_changed`, and colour-dialog pause through `on_color_dialog`, in the audio check. `native_pause_check` covers real focus loss for movement, without asserting audio.
- Mid-run failure was tested by posting a bus error against fakesink. A device or PipeWire dying during real play was not exercised.
- Only pipewiresink has real-output evidence. alsasink is untested; pulsesink and autoaudiosink are not installed here.
- End-to-end latency was not measured.
- A resumed melody may lose its first moments to stream opening; the fidelity check covers cues, not melody resumes.
