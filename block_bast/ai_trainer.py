import json
import os
import random
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

SHARED_WEIGHTS_PATH = os.path.join(_ROOT, "shared", "weights.json")

STATS_FILE         = os.path.join(_HERE, "stats.json")
WEIGHTS_FILE       = os.path.join(_HERE, "weights.json")
BEST_FILE          = os.path.join(_HERE, "best_weights.json")
POPULATION_FILE    = os.path.join(_HERE, "population.json")
CURRENT_INDEX_FILE = os.path.join(_HERE, "current_index.json")
LOG_FILE           = os.path.join(_HERE, "training_log.json")

POPULATION_SIZE = 12
TOP_KEEP        = 3
MUTATE_RATE     = 0.25
MUTATE_POWER    = 0.20
TOURNAMENT_K    = 3

BOUNDS = {
    "holes":              (-15.0,  -1.0),
    "max_height":          (-8.0,  -0.5),
    "avg_height":          (-5.0,  -0.1),
    "filled":              (-2.0,   0.0),
    "edge_penalty":        (-5.0,   0.0),
    "cluster_score":        (0.0,  10.0),
    "row_almost_full":      (5.0,  30.0),
    "col_almost_full":      (5.0,  30.0),
    "empty_rows":           (0.0,  15.0),
    "combo_preservation":  (20.0, 100.0),
    "piece_fit":            (2.0,  20.0),
    "diversity":            (0.0,  10.0),
    "cleared_lines":       (50.0, 200.0),
    "immediate_gain":       (0.0,   5.0),
}

def load_json(path):
    """Safely loads a JSON file. Returns None on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_json(path, data):
    """Saves data to a JSON file atomically (temp-file + rename)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    if os.path.exists(path):
        os.remove(path)
    os.rename(tmp, path)


def calc_fitness(stats: dict) -> float:
    """Weighted combination of avg moves, avg score, avg combo."""
    if not stats:
        return 0.0

    games     = list(stats.values())
    n         = len(games)
    avg_moves = sum(g["Moves"]     for g in games) / n
    avg_score = sum(g["Score"]     for g in games) / n
    avg_combo = sum(g["Max_Combo"] for g in games) / n

    return avg_moves * 1.0 + avg_score * 0.02 + avg_combo * 3.0


def random_weights() -> dict:
    """Generates a random weight vector within BOUNDS."""
    return {k: random.uniform(lo, hi) for k, (lo, hi) in BOUNDS.items()}


def mutate(w: dict) -> dict:
    """Applies Gaussian mutation to each gene with probability MUTATE_RATE."""
    result = w.copy()
    for k in result:
        if random.random() < MUTATE_RATE:
            lo, hi = BOUNDS[k]
            result[k] += random.gauss(0, (hi - lo) * MUTATE_POWER)
            result[k]  = max(lo, min(hi, result[k]))
    return result


def crossover(w1: dict, w2: dict) -> dict:
    """Uniform crossover — each gene taken from one of the two parents."""
    return {k: w1[k] if random.random() < 0.5 else w2[k] for k in w1}


def tournament_select(population: list) -> dict:
    """Selects the fittest individual from a random subset."""
    contestants = random.sample(population, min(TOURNAMENT_K, len(population)))
    return max(contestants, key=lambda x: x["f"])


def log_generation(stats: dict) -> None:
    log = load_json(LOG_FILE) or {}

    generation = len(log) + 1

    scores = [stats[g]["Score"]     for g in stats]
    combos = [stats[g]["Max_Combo"] for g in stats]
    moves  = [stats[g]["Moves"]     for g in stats]

    log[str(generation)] = {
        "avg_score":  round(sum(scores) / len(scores), 2),
        "best_score": max(scores),
        "avg_combo":  round(sum(combos) / len(combos), 2),
        "max_combo":  max(combos),
        "avg_moves":  round(sum(moves)  / len(moves),  2),
    }

    save_json(LOG_FILE, log)
    print(f"  📈 Generation {generation} logged — "
          f"avg_score={log[str(generation)]['avg_score']} "
          f"best={log[str(generation)]['best_score']}")

def train() -> None:
    stats = load_json(STATS_FILE)
    if not stats:
        print(" train() called but stats.json is empty — skipping")
        return

    population  = load_json(POPULATION_FILE)
    current_idx = load_json(CURRENT_INDEX_FILE)

    if not population:
        seed = load_json(SHARED_WEIGHTS_PATH) or random_weights()
        population = [{"w": random_weights(), "f": None}
                      for _ in range(POPULATION_SIZE)]
        population[0]["w"] = seed       # seed with best known weights
        current_idx = 0

    if current_idx is None:
        current_idx = 0

    fitness = calc_fitness(stats)
    population[current_idx]["f"] = fitness
    print(f" Individual {current_idx + 1}/{POPULATION_SIZE}  "
          f"fitness: {fitness:.2f}")

    all_evaluated = all(p["f"] is not None for p in population)

    if all_evaluated:
        log_generation(stats)

        population.sort(key=lambda x: x["f"], reverse=True)

        # Save best weights to shared/ if improved
        best_record  = load_json(BEST_FILE)
        best_fitness = best_record.get("f", 0.0) if isinstance(best_record, dict) else 0.0

        if population[0]["f"] > best_fitness:
            print(f"  🏆 New record! {population[0]['f']:.2f} "
                  f"(was {best_fitness:.2f})")
            save_json(BEST_FILE,          {"w": population[0]["w"],
                                           "f": population[0]["f"]})
            save_json(SHARED_WEIGHTS_PATH, population[0]["w"])
        else:
            print(f"  — No improvement (best so far: {best_fitness:.2f})")

        new_pop = [deepcopy(p) for p in population[:TOP_KEEP]]
        while len(new_pop) < POPULATION_SIZE:
            p1    = tournament_select(population)
            p2    = tournament_select(population)
            child = {"w": mutate(crossover(p1["w"], p2["w"])), "f": None}
            new_pop.append(child)

        population  = new_pop
        current_idx = 0

    else:
        current_idx += 1
        while (current_idx < len(population)
               and population[current_idx]["f"] is not None):
            current_idx += 1
        if current_idx >= len(population):
            current_idx = 0


    save_json(POPULATION_FILE,    population)
    save_json(CURRENT_INDEX_FILE, current_idx)
    save_json(WEIGHTS_FILE,       population[current_idx]["w"])


if __name__ == "__main__":
    train()