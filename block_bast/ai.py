import json
import os
import sys
import time
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)

from shared.ai_core import (
    choose_best_move_2ply,
    FALLBACK_WEIGHTS,
    load_weights,
    load_state,
    choose_best_move,
)
import ai_trainer


_SHARED_DIR = os.path.join(_ROOT, "shared")

SHARED_WEIGHTS_PATH = os.path.join(_SHARED_DIR, "weights.json")  
LOCAL_WEIGHTS_PATH  = os.path.join(_HERE,        "weights.json")   

STATE_PATH   = os.path.join(_HERE, "state.json")
ACTION_PATH  = os.path.join(_HERE, "action.json")
RESTART_PATH = os.path.join(_HERE, "restart.json")
STATS_PATH   = os.path.join(_HERE, "stats.json")

POLL_DELAY_SEC    = 0.05
MOVE_COOLDOWN_SEC = 0.02

GAMES_PER_INDIVIDUAL = ai_trainer.POPULATION_SIZE   # ігор на одного індивіда



def write_action(slot: int, gx: int, gy: int, move_id: int) -> None:
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
    """Runs in a daemon thread; lets the user type on/off/quit."""
    print("AI Control:  on | off | quit")
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "on":
            toggle.set(True)
            print("✅ AI enabled")
        elif cmd == "off":
            toggle.set(False)
            print("⏸  AI paused")
        elif cmd in ("quit", "exit", "q"):
            toggle.set(False)
            print("👋 Exiting...")
            os._exit(0)
        else:
            print("Commands: on / off / quit")



def main() -> None:
    toggle = Toggle()

    try:
        with open(STATS_PATH, "r", encoding="utf-8") as f:
            stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        stats = {}

    threading.Thread(target=console_thread, args=(toggle,), daemon=True).start()

    move_id    = 0
    game       = 1
    generation = 1
    max_combo  = 0
    max_score  = 0

    weights = load_weights(SHARED_WEIGHTS_PATH, FALLBACK_WEIGHTS)
    print(f"Loaded seed weights from shared/weights.json")
    print("AI started! Type 'on' to begin.")

    while True:
        if not toggle.get():
            time.sleep(0.1)
            continue

        time.sleep(POLL_DELAY_SEC)

        state = load_state(STATE_PATH)

        if state is None:
            stats[game] = {
                "Moves":     move_id,
                "Score":     max_score,
                "Max_Combo": max_combo,
            }
            with open(STATS_PATH, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)

            print(
                f"  Game {game:>2} over — "
                f"moves={move_id}  score={max_score}  combo={max_combo}"
            )

            game     += 1
            move_id   = 0
            max_combo = 0
            max_score = 0

            if game > GAMES_PER_INDIVIDUAL:
                print(f"\nGeneration {generation} — evaluating individual...")
                ai_trainer.train()

                import json as _json
                try:
                    with open(ai_trainer.CURRENT_INDEX_FILE) as cf:
                        idx = _json.load(cf)
                except Exception:
                    idx = 0

                if idx == 0:
                    generation += 1
                    print(f"🔄 New generation {generation} started.\n")

                weights = load_weights(LOCAL_WEIGHTS_PATH, FALLBACK_WEIGHTS)

                game  = 1
                stats = {}

            with open(RESTART_PATH, "w", encoding="utf-8") as f:
                json.dump({"restart": True}, f, ensure_ascii=False, indent=2)

            continue

        max_combo = max(max_combo, state.combo)
        max_score = max(max_score, state.score)

        best = choose_best_move_2ply(state, weights)
        if best is None:
            continue

        slot, gx, gy = best
        move_id += 1
        write_action(slot, gx, gy, move_id)
        print(
            f"Gen {generation:>3}  Game {game:>2}  Move #{move_id:>4} "
            f"Score {state.score:>6}  Combo {state.combo}"
        )
        time.sleep(MOVE_COOLDOWN_SEC)


if __name__ == "__main__":
    main()
