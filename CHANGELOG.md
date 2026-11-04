# Changelog

## Unreleased

- Add the MIT License, selected by the owner after the initial public release, with copyright attributed to Martin Kirwin (KirkShader).
- Document permission for commercial use and the requirement to retain the copyright and permission notices.
- Leave the original `v0.0001` tag and published release unchanged.
- Add a minimal Omarchy bar launcher plugin (`io.github.kirkshader.omarchy-snake`) that opens the existing GTK game on click, as a prerequisite for marketplace submission. The game itself and its version are unchanged.

## 0.0001 — Initial Public offering

First public source release of Omarchy Snake, a native, offline Python/GTK4 game built for Omarchy.

### Included
- Easy, Normal and Hard modes; safe two-turn buffering; orange growth rewards and green shrinking rewards.
- Two-stage difficulty chooser: preview the rules, then Start or Back.
- Escape pause/resume and independent menu, dialog and focus pause handling.
- Automatic display fitting, board zoom, theme-aware presentation and configurable colours.
- Game Over and full-board Victory states, with saved best scores per difficulty.
- Original synthesized retro sound effects for collections, start, loss and victory.
- Quiet monophonic music that pauses with play; independent Music/Sound Effects switches and saved master volume.
- Optional GStreamer audio with silent fallback when unavailable.

### Verification
- 218 automated unit tests passed.
- Eight native test scripts passed sequentially, including actual PipeWire output capture and cue-duration checks.
- Independent audio code review found no actionable defects.
- The owner play-tested and approved the result.

### Distribution notes
- Source release: dependencies are installed separately; see README.md.
- No one-click installer, packaged launcher or Omarchy Hub submission is included.
- Saved preferences and high scores remain in the player's XDG directories, outside the repository.
- No license grant is added by this release; a software license has not yet been selected.
