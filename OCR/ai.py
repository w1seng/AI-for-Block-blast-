import json
import os
import sys
import time
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from shared.ai_core import (
    FALLBACK_WEIGHTS,
    load_weights,
    load_state,
    choose_best_move,
    Piece,
    GameState,
)


_SHARED_DIR = os.path.join(_ROOT, "shared")

# Shared with block_bast — reads the weights trained there.
WEIGHTS_PATH = os.path.join(_SHARED_DIR, "weights.json")

STATE_PATH   = os.path.join(_HERE, "state.json")
ACTION_PATH  = os.path.join(_HERE, "action.json")

POLL_DELAY_SEC = 0.05



def write_action(slot: int, gx: int, gy: int, move_id: int) -> None:
    """Writes the best-move hint to action.json for the overlay (game.py) to read."""
    payload  = {"move_id": move_id, "slot": slot, "gx": gx, "gy": gy}
    tmp_path = ACTION_PATH + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    for attempt in range(5):
        try:
            if os.path.exists(ACTION_PATH):
                os.remove(ACTION_PATH)
            os.rename(tmp_path, ACTION_PATH)
            return
        except PermissionError:
            if attempt < 4:
                time.sleep(0.05)
            else:
                print("⚠️  Failed to write action.json after 5 attempts")
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise

class Toggle:
    """Thread-safe on/off switch for the hint loop."""

    def __init__(self) -> None:
        self._enabled = False
        self._lock    = threading.Lock()

    def set(self, value: bool) -> None:
        with self._lock:
            self._enabled = value

    def get(self) -> bool:
        with self._lock:
            return self._enabled


def console_thread(toggle: Toggle) -> None:
    """Daemon thread — lets the user enable/disable hints at runtime."""
    print("🤖 OCR Hint AI:  on | off | quit")
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "on":
            toggle.set(True)
            print("✅ Hints enabled")
        elif cmd == "off":
            toggle.set(False)
            print("⏸  Hints paused")
        elif cmd in ("quit", "exit", "q"):
            toggle.set(False)
            print("👋 Exiting...")
            os._exit(0)
        else:
            print("❌ Commands: on / off / quit")


def main() -> None:
    """Hint loop for the OCR overlay.

    Reads state.json produced by state_OCR.py, calculates the best move with
    the shared weights, and writes action.json for game.py to display.

    No training here — weights come from block_bast's genetic trainer.
    """
    toggle = Toggle()
    threading.Thread(target=console_thread, args=(toggle,), daemon=True).start()

    weights  = load_weights(WEIGHTS_PATH, FALLBACK_WEIGHTS)
    move_id  = 0

    print("🎮 OCR AI started! Type 'on' to enable hints.")

    while True:
        if not toggle.get():
            time.sleep(0.1)
            continue

        time.sleep(POLL_DELAY_SEC)

        state = load_state(STATE_PATH)
        if state is None:
            continue

        best = choose_best_move(state, weights)
        if best is None:
            continue

        slot, gx, gy = best
        move_id += 1
        write_action(slot, gx, gy, move_id)
        print(f"Hint #{move_id:>4}  slot={slot}  ({gx}, {gy})  score={state.score}")


if __name__ == "__main__":
    main()