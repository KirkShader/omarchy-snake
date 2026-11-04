# Approval record — Omarchy Snake

## Marketplace submission owner confirmation — 2026-11-04

After being shown the complete submission draft, the owner explicitly approved title `[Plugin]: Omarchy Snake`, repository `KirkShader/omarchy-snake`, category `Other`, and tags `games, bar, launcher`, and confirmed all five upstream submission checklist statements, including ownership/permission and the distinction between listing approval and a security guarantee. Submit after independent launcher review passes; verify the returned issue and automated validation without claiming maintainer approval.

## Approved marketplace launcher prerequisite — 2026-11-04 (MARKETPLACE_BRIEF.md)

The current submission request authorizes the minimal installable bar launcher the marketplace requires for the existing GTK game: root `manifest.json`, `BarWidget.qml` and the owner's original `omarchy-snake.svg`, with tests and documentation. It launches `grid_preview.py --show-difficulty` from the plugin's own checkout on user activation only. It does not authorize gameplay changes, a QML rewrite, a new game version, a licence change, moving the `v0.0001` tag, package installs, changes to the user's bar or home configuration, or claiming a listing before human marketplace maintainers approve one.

## Approved license publication and marketplace submission — 2026-11-04

The user approved a final commit/push of the MIT license and associated documentation, and requested submission to the Omarchy website's games listing. This supersedes the earlier local-only license restriction. Any marketplace listing remains subject to that site's required packaging, validation and maintainer approval; a submitted request is not a published listing. Do not move the existing `v0.0001` tag or claim approval on behalf of marketplace maintainers.

## Approved license selection — 2026-11-04

After the commercial-use distinction was explained, the user explicitly chose the MIT License. This supersedes the earlier noncommercial preference and authorizes adding the standard MIT text and matching documentation locally. It does not authorize a new commit, push, release update, retagging or Omarchy Hub submission.

## Approved first public source release — 2026-11-04

The user approved committing and pushing the completed, play-tested game as version `0.0001`, and explicitly selected making `KirkShader/omarchy-snake` public and publishing GitHub release `v0.0001` titled `Initial Public offering`. This supersedes earlier no-commit/no-push/private-only boundaries for this release only. It includes release metadata and public download instructions; it does not authorize an Omarchy Hub submission, package installation, a software-license choice or unrelated changes.

## Current working agreement

The original multi-bot plan in PLAN.md is historical. The user paused that setup and subsequently approved direct, incremental development with the coordinator in this chat. The specialist profiles remain parked; their creation is not proof of working model authentication. Do not restart them, repeat logins, or change credentials without fresh permission.

## Authorized and exercised preview slices

- Create and run a native, offline GTK preview on workspace 1, without installing dependencies or a desktop launcher.
- Fixed cell size: 16 × 16 pixels, independent of playing-area dimensions. Approved presets: Easy 64 × 64 cells / 1024 × 1024 pixels; Normal 48 × 48 / 768 × 768; Hard 32 × 32 / 512 × 512. All start at one cell per 0.15 seconds; Easy and Normal remain at that speed, while Hard accelerates as specified below.
- White translucent grid lines over an opaque, almost-black background.
- Six-square initial snake with discrete cell-by-cell movement.
- Arrow-key steering and direction marker on the head; immediate reverse turns ignored. Easy and Normal wrap at all four edges. Hard has solid outer walls: leaving the playing area ends the run without wrapping.
- Exact-app Omarchy opacity exception, with the user configuration backed up and validated; no packaged Omarchy files modified.
- Latest requested appearance slice: an outer frame matching the text's off-white, thicker than the grid lines, solid white at its outer edge and fading inward to black. Keep the frame outside the unchanged playable board.
- Relevant project-local tests and exact-preview replacement for each authorized slice.
- Header title: Omarchy Snake, centered at 18px; Menu aligned with the board border. Surrounding UI follows the active Omarchy palette. The menu has enabled New Game, Options, and Quit, inside the matching gradient frame.
- New Game opens a centered Easy / Normal / Hard chooser with Cancel. Movement and the green-dot cooldown pause while the chooser is open. Cancel resumes the existing run; choosing a preset resets the run and resizes the actual board without scaling cells.
- Options opens an appearance submenu with native Border colour and Grid-line colour pickers and Back. Border colour affects both the board and dropdown and keeps the inward fade. Changes apply immediately and survive new games in the same application session; persistence across application launches has not been requested.
- Core mechanics now authorized: five simultaneous orange dots on Easy and Normal, ten on Hard. Each gives one point and grows the snake by one square, then is immediately replaced in a free cell. Dots cannot overlap one another or the body. The last three body squares fade from body green toward an almost-black tip.
- Green dots may spawn only when the current length is at least six; collecting one removes exactly two tail squares and does not change the score. No green dots at length four or five. The earlier randomized interval is superseded by a 30-second eligible-play cooldown, one green dot at a time; after collection a new full cooldown starts. An existing dot remains until collected rather than stacking more dots.
- On Easy and Normal, self-collision ends the run at a current length of ten or more; shorter snakes can cross themselves. On Hard, self-collision is fatal from the start, with no length threshold. Moving into a vacating tail cell remains safe on every difficulty. Menu → New Game resets score, dots, length, direction and game-over state.
- Hard-only speed trial: each collected orange reduces the time between steps by 0.0023 seconds (2.3 ms), cumulatively from 0.150 seconds. The previous 0.001-second proposal is superseded. Green dots do not undo acceleration. A new run resets speed. No proposed 0.050-second gameplay cap was approved or applied; a 1 ms technical minimum prevents zero/negative timer intervals. GTK schedules rounded whole-millisecond delays, while the status shows the nominal configured interval. Movement timers are replaced rather than duplicated when speed changes and stop on game over. Green-dot cooldown still measures elapsed active play, not movement-step count.
- Game-over presentation: board border and grid temporarily use reserved red #FF3333; a large centered Game Over box appears with a New Game button beneath it. The button opens the difficulty chooser, Cancel restores the Game Over panel, and a new run restores the player's selected board colours. The exact reserved shade cannot be applied through either Options picker; rejection restores the previous setting and shows an explanation. No global desktop settings or launcher installation are included in this change.
- Private GitHub backup: the user approved preparing a private repository named `omarchy-snake` containing the existing game source, tests, project notes and a restore/run guide. Git initialization, a backup commit and upload to that private repository are authorized for this backup. Exclude credentials, caches, logs and recordings. Verify remote privacy and uploaded contents before calling the backup complete. Browser sign-in is completed by the user; never request passwords or tokens in chat. This does not authorize making the project public, installing dependencies, changing game behaviour or modifying disk partitions.

## Not authorized by these preview requests

- Starting specialist bots, further authentication changes, scheduled or autonomous work.
- Installing additional dependencies, system packages, desktop launchers or application-menu entries.
- Adding difficulty modes, settings, persistence, or other gameplay beyond the specifically approved controls above.
- Public publishing, distributing the project or making unrelated commits; the private backup explicitly approved above is the exception.

The user requests and evaluates each slice. Stop after the current change and wait for feedback before adding another feature. Ideas in IDEAS.md are unimplemented proposals, not approval to build them.

## Approved polish — 2026-10-31

The user approved the joint review's recommendations as a complete polish scope (recorded in the working brief), with these explicit decisions. Where they conflict, they supersede the entries above; the history above stays as the record of earlier approvals.

- **Balanced Hard:** keep 150 ms − 2.3 ms per orange, now with a **50 ms gameplay floor**. The user explicitly chose this, superseding the earlier "no 0.050-second cap" and the 1 ms technical floor. Green dots never undo speed; New Game resets to 150 ms. No separate unlimited mode.
- **Escape** toggles a manual pause. Menu, Options, colour chooser, difficulty chooser and focus loss pause for separate reasons, and closing one never resumes another. Focus loss engages the manual pause after 0.3 s; regaining focus does not resume. No pause after loss or victory.
- **Display fit / zoom:** cell counts and rules are unchanged; only the rendered cell size changes. Default 16 logical px, shrinking to fit the monitor. Auto fit and 50–200% zoom are available; below 6 px the board scrolls. Monitor settings are never changed. This supersedes the strictly fixed 16 px presentation.
- **Victory state** when the snake covers every cell; the last orange scores. Distinct from Game Over.
- **Accessibility:** readable overlay buttons under light and dark palettes; a green diamond versus an orange round dot; a more visible tail tip; Score, Length and Best in the header; rule explanations in the chooser; modal focus trap with focus return; states named in text.
- **Two-deep safe turn queue:** supersedes the one-turn-per-tick rule; reversals and overflow are rejected.
- **Persistence:** best score per difficulty, plus colours and zoom, in versioned XDG JSON (atomic, validated, reserved red rejected). Supersedes "session-only colours; no persistence".
- **Engineering:** split into the `omarchy_snake` package with the `grid_preview.py` façade; optional `--verbose` / `--debug` logging that cannot stop gameplay; a single owned movement timer with no catch-up; second launch refocuses the existing window; native checks use isolated app IDs and temporary data.

Still not authorized: installs, launchers, system or Hyprland setting changes, public publishing, commits or pushes without a fresh request, bots, network features, and gameplay beyond the above.

## Approved revision — two-stage New Game (2026-11-01, NEW_GAME_FLOW_BRIEF.md)

Supersedes only the one-click difficulty start (and the chooser's Cancel button):
- First page: a small title and only Easy / Normal / Hard. Esc cancels, preserving the current run, loss, victory or manual pause.
- Choosing a difficulty opens a second page with that difficulty's name and rules, plus Back and Start. It never resets, moves or rescores the run. Start alone commits and resets; Back returns to the first page.
- Both pages keep the difficulty pause reason. Esc on details goes back first. Focus is trapped per page; Enter/Space must be released before a new page responds.
- Menu, Paused, Game Over, Victory and `--show-difficulty` use the same flow.

Not authorized by it: audio (the user only asked whether it is possible), toolbar icon changes, installs, system/global config changes, commits, pushes or data resets.

## Approved audio — 2026-11-04 (AUDIO_BRIEF.md)

The user approved retro arcade sounds and a quiet monophonic music loop. This supersedes the earlier exclusion of audio only; game rules, board sizing, chooser flow, pauses, scores, appearance settings and single-instance behaviour stay as they were.

- Original offline synthesized cues: orange, green, new game actually starting, game over, victory. No sound on movement, previewing, Back or cancelling.
- A quiet looping melody only during active play.
- Options: separate Music and Sound Effects switches and a master volume, saved in the existing schema-v1 settings. Defaults: 30%, both on, music quieter than effects. Volume 0 silences both.
- Silent gameplay, with bounded diagnostics, when audio libraries, plugins or devices are unavailable.

Not authorized by it: publishing or Omarchy Hub submission (a possible future discussion only), making the repository public, commits, pushes, packaging or installing, desktop or global config changes, audio device or group changes, subprocess-per-sound playback or network use.
