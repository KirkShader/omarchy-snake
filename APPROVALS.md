# Approval record — Omarchy Snake

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
