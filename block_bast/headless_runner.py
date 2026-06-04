import argparse
import json
import os
import sys
import time


_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)


from block_bast.game import Game
from shared.ai_core import (
    FALLBACK_WEIGHTS,
    GameState,
    Piece as AIPiece,
    choose_best_move,
    find_all_legal_moves,
    load_weights,
)
import block_bast.ai_trainer as ai_trainer

SHARED_WEIGHTS = os.path.join(_ROOT, "shared", "weights.json")
LOCAL_WEIGHTS  = os.path.join(_HERE, "weights.json")   
STATS_PATH     = os.path.join(_HERE, "stats.json")     

def game_to_state(game: Game) -> GameState:
    """Converts a live Game object into a GameState the AI understands."""
    hand = [None, None, None]
    for i, piece in enumerate(game.hand):
        if piece is not None:
            hand[i] = AIPiece(cells=list(piece.cells), slot=i)

    return GameState(
        grid        = [row[:] for row in game.grid],
        hand        = hand,
        combo       = game.combo,
        combo_active= game.combo > 0,
        score       = game.score,
        size        = game.size,
    )


def run_one_game(weights: dict) -> dict:
    game = Game()
    game.deal_hand_full()

    moves     = 0
    max_combo = 0

    while True:
        state = game_to_state(game)

        # Game over — no legal move exists for any piece in hand
        if not find_all_legal_moves(state):
            break

        best = choose_best_move(state, weights)
        if best is None:
            break

        slot, gx, gy = best

        game.place(slot, gx, gy)
        moves     += 1
        max_combo  = max(max_combo, game.combo)

        # Deal new hand once all 3 slots are used
        if all(p is None for p in game.hand):
            game.deal_hand_full()

    return {
        "Moves":     moves,
        "Score":     game.score,
        "Max_Combo": max_combo,
    }


def main(games_per_individual: int = 12) -> None:

    weights    = load_weights(LOCAL_WEIGHTS,
                              load_weights(SHARED_WEIGHTS, FALLBACK_WEIGHTS))
    generation = 1
    individual = 1
    total_games= 0
    run_start  = time.time()

    print("╔══════════════════════════════════════════════╗")
    print("║        Block Blast — Headless Trainer        ║")
    print("╚══════════════════════════════════════════════╝")
    print(f"  Games per individual : {games_per_individual}")
    print(f"  Population size      : {ai_trainer.POPULATION_SIZE}")
    print(f"  Weights file         : {SHARED_WEIGHTS}")
    print()

    try:
        while True:
            print(f"── Gen {generation}  Individual {individual}/{ai_trainer.POPULATION_SIZE} "
                  f"{'─' * 20}")

            stats      = {}
            ind_start  = time.time()
            best_score = 0

            for g in range(1, games_per_individual + 1):
                result      = run_one_game(weights)
                stats[str(g)] = result
                total_games += 1
                best_score   = max(best_score, result["Score"])

                elapsed = time.time() - run_start
                print(
                    f"  [{g:>2}/{games_per_individual}]  "
                    f"score={result['Score']:>14,}  "
                    f"moves={result['Moves']:>6}  "
                    f"combo={result['Max_Combo']:>2}  "
                    f"elapsed={elapsed:.0f}s"
                )

            ind_time = time.time() - ind_start
            avg_score = sum(s["Score"] for s in stats.values()) / len(stats)
            print(
                f"  → avg={avg_score:>12,.0f}  "
                f"best={best_score:>12,}  "
                f"time={ind_time:.1f}s\n"
            )

            with open(STATS_PATH, "w", encoding="utf-8") as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)

            # Evolve
            ai_trainer.train()
            weights = load_weights(LOCAL_WEIGHTS, FALLBACK_WEIGHTS)

            individual += 1
            if individual > ai_trainer.POPULATION_SIZE:
                individual  = 1
                generation += 1

    except KeyboardInterrupt:
        total_time = time.time() - run_start
        print(f"\n\n⏹  Stopped after {total_games} games "
              f"({total_time / 60:.1f} min)")
        print(f"   Best weights saved to: {SHARED_WEIGHTS}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Headless Block Blast AI trainer (no display needed)"
    )
    parser.add_argument(
        "--games",
        type=int,
        default=12,
        metavar="N",
        help="Number of games per individual (default: 12)",
    )
    args = parser.parse_args()
    main(games_per_individual=args.games)
