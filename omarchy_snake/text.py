"""Player-facing text: HUD, status line and difficulty explanations."""
from .rules import DIFFICULTIES, HARD_MIN_STEP_INTERVAL_MS, HARD_SPEEDUP_MS, STEP_INTERVAL_MS

_STEADY = f'steady {STEP_INTERVAL_MS / 1000:g} s pace'
DIFFICULTY_DETAILS = {
    'Easy': f'{DIFFICULTIES["Easy"]} × {DIFFICULTIES["Easy"]} board\nEdges wrap around\n'
            f'Self-hits fatal from length 10\n5 oranges · {_STEADY}',
    'Normal': f'{DIFFICULTIES["Normal"]} × {DIFFICULTIES["Normal"]} board\nEdges wrap around\n'
              f'Self-hits fatal from length 10\n5 oranges · {_STEADY}',
    'Hard': f'{DIFFICULTIES["Hard"]} × {DIFFICULTIES["Hard"]} board\nSolid walls\n'
            f'Any self-hit is fatal\n10 oranges · each speeds up {HARD_SPEEDUP_MS:g} ms,\n'
            f'down to {HARD_MIN_STEP_INTERVAL_MS / 1000:g} s per cell',
}
REWARD_HELP = ('Orange ● +1 point and +1 length.  Green ◆ appears after 30 s of play at length 6+:'
               ' −2 length, score kept.  Fill every cell to win.  Esc pauses.')


def hud_text(game, best):
    return (f'Score {game.score}  ·  Length {len(game.snake)}  ·  '
            f'Best {max(best, game.score)}')


def status_text(game, paused, manual=True):
    if game.won:
        return 'Board complete — every cell filled! Choose New Game to play again.'
    if game.game_over:
        return f'Game over — {game.game_over_reason}. Choose New Game to restart.'
    if paused and manual:
        return 'Paused — press Esc or Resume to continue.'
    if paused:
        return 'Paused while a menu, chooser or dialog is open.'
    edges = 'Solid walls' if game.difficulty == 'Hard' else 'Edge wrap'
    return (f'Arrow keys steer  ·  Esc pauses  ·  1 cell / {game.step_interval_ms / 1000:g} sec'
            f'  ·  {edges}')
