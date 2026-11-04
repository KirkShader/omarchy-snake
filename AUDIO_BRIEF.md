# Approved audio slice — 2026-11-04

## Authority and scope
The user approved the coordinator's proposed retro arcade sounds and quiet monophonic music loop, with Claude Code implementing and Hermes independently reviewing/testing. This explicitly supersedes the previous briefs' exclusion of audio ONLY. Keep all existing game rules, board sizing, chooser flow, pauses, scores, appearance settings and single-instance behavior intact. The user may later submit to Omarchy Hub; that is future discussion, NOT authority to publish, make the repo public, commit, push, package/install, change desktop/global config, or submit anything.

## Deliverable
Implement original offline synthesized arcade audio:
- Orange collected: short bright beep.
- Green collected: two descending notes, clearly distinct.
- New game actually starts: quick three-note cue (a sound cue, not a new delayed countdown mechanic). No cue on difficulty preview/Back/cancel.
- Game over: low descending buzz.
- Victory: short celebratory jingle.
- Quiet repeating monophonic (one musical note at a time) retro electronic melody ONLY during active play. No per-movement beeps; no music at chooser startup, during any pause reason, after game over/victory, or after shutdown.
- Menu Options: separate Music and Sound Effects switches and master volume, saved across launches. Defaults modest (e.g. 30% master, music internally quieter than SFX), both switches enabled. Volume 0 genuinely silences both; changes apply immediately; disabled channels do not get resurrected by pause/resume/new game. Options already pause the game and must remain usable with keyboard.
- Music resumes cleanly only when GameSession.running is true. Pause active SFX too or stop them; never leak long jingles across restart/close. Avoid repeated cues on redraw, finish notifications or each step. Correctly detect orange+victory together, green, collision without reward, and no reward by merely previewing a chooser.
- Fail gracefully to silent gameplay when audio libraries/devices/plugins unavailable, with bounded useful diagnostics under existing logging. Do not swallow arbitrary gameplay exceptions. No subprocess per sound, network calls, audio devices/groups/global changes or package installs.
- Preserve existing settings/scores and schema-v1 compatibility. Validate bools/volume strictly, reject nonfinite/nonnumeric values; keep colors and zoom on save. Do not overwrite the user's real settings while testing.

## Engineering constraints and discovery
Repo /home/bignutta/Work/omarchy-snake has extensive PREEXISTING UNCOMMITTED work. Preserve it all, no git reset/checkout/clean/commit/push. Baseline coordinator verified 139 unittest tests passing today. No live game is currently running. Tests must use separate app IDs/temp state and run native scripts sequentially. TMPDIR and OMARCHY_SNAKE_SCRATCH must point inside /home/bignutta/.hermes/cache/scratch, NOT /tmp.

System Python /usr/bin/python has GI, GTK4 and GStreamer 1.28.8. GStreamer playbin, audioconvert, audioresample, pipewiresink exist, but WAVPARSE, PULSESINK and AUTOAUDIOSINK DO NOT. Therefore don't assume WAV playback via playbin works. Probe appsrc/volume and consider synthesized PCM via appsrc + volume + audioconvert + audioresample + pipewiresink (no WAV decoding plugins). Choose a portable fallback sink when available but do not assume plugins. Make backend import optional and headless tests GI-independent. No need for heavyweight external Python dependencies. Original deterministic synthesis in a small module is suitable; generated artifacts must be local, original and reproducible without network. Keep buffers bounded, reuse resources, release bus watches/pipelines/timers on stop/shutdown, and ensure no stale callbacks resurrect playback.

Consult primary GStreamer docs or runtime introspection when API details uncertain. Update README including optional audio runtime prerequisites/fallback behavior; don't claim bundled codecs or an installer. Update APPROVALS and relevant IDEAS. Explain original audio provenance in README. Project-local artifacts only.

## Test-first requirement
Use vertical RED -> GREEN -> REFACTOR slices, starting with one minimal test, not a giant speculative test pile. Record real failing command/assertion evidence then passing output in AUDIO_TEST_LOG.md. Unit-test synthesis bounds/format/silence/envelopes, preference backward compatibility, invalid settings, independent toggles/volume, controller lifecycle/pause reasons/cues/cleanup/failure. Test actual Gst backend lifecycle and real native GTK settings/collection/finish paths in an isolated native_audio_check.py, not only mocks. Native check should avoid changing real scores/preferences. Ensure genuine running audio pipeline and collect timing/errors; hearing quality still requires user evaluation. Keep tests deterministic and small. Don't run native scripts concurrently.

Run /usr/bin/python -m unittest discover -s tests -q and new audio native checks, then relevant old native checks. Do not weaken old tests to fit regressions. Do not run endlessly if backend is missing; report explicit skip/failure rather than fabricate successful audio. Preserve no-live-game state after tests.

## Result
Return a concise report of files changed, red/green evidence, actual commands and test totals, backend exercised and limitations. State failures honestly. Do not commit/push or launch an indefinite user game. Leave work ready for Hermes independent verification and user listening test.
