import json
import os
import random
from copy import deepcopy

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

SHARED_WEIGHTS_PATH = os.path.join(_ROOT, "shared", "weights.json")


STATS_FILE          = os.path.join(_HERE, "stats.json")
WEIGHTS_FILE        = os.path.join(_HERE, "weights.json")        
BEST_FILE           = os.path.join(_HERE, "best_weights.json")   
POPULATION_FILE     = os.path.join(_HERE, "population.json")
CURRENT_INDEX_FILE  = os.path.join(_HERE, "current_index.json")


POPULATION_SIZE   = 12     
TOP_KEEP          = 3      
MUTATE_RATE       = 0.25   
MUTATE_POWER      = 0.20   
TOURNAMENT_K      = 3      

BOUNDS = {
    'holes':              (-15.0, -1.0),
    'max_height':          (-8.0, -0.5),
    'avg_height':          (-5.0, -0.1),
    'filled':              (-2.0,  0.0),
    'edge_penalty':        (-5.0,  0.0),
    'cluster_score':        (0.0, 10.0),
    'row_almost_full':      (5.0, 30.0),
    'col_almost_full':      (5.0, 30.0),
    'empty_rows':           (0.0, 15.0),
    'combo_preservation':  (20.0, 100.0),
    'piece_fit':            (2.0,  20.0),
    'diversity':            (0.0,  10.0),
    'cleared_lines':       (50.0, 200.0),
    'immediate_gain':       (0.0,   5.0),
}


def load_json(path):
    """Safely loads a JSON file. Returns None on any error."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def save_json(path, data):
    """Saves data to a JSON file."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def calc_fitness(stats):

    if not stats:
        return 0.0
    games = list(stats.values())
    n = len(games)

    avg_moves = sum(g['Moves'] for g in games) / n
    avg_score = sum(g['Score'] for g in games) / n
    avg_combo = sum(g['Max_Combo'] for g in games) / n

  
    return avg_moves * 1.0 + avg_score * 0.02 + avg_combo * 3.0



def random_weights():

    return {k: random.uniform(v[0], v[1]) for k, v in BOUNDS.items()}


def mutate(w):

    new = w.copy()
    for k in new:
        if random.random() < MUTATE_RATE:
            mn, mx = BOUNDS[k]
            sigma = (mx - mn) * MUTATE_POWER
            new[k] += random.gauss(0, sigma)
            new[k] = max(mn, min(mx, new[k]))
    return new


def crossover(w1, w2):
    """Uniform crossover — кожен ген береться від одного з батьків."""
    return {k: w1[k] if random.random() < 0.5 else w2[k] for k in w1}


def tournament_select(population, k=TOURNAMENT_K):

    contestants = random.sample(population, min(k, len(population)))
    return max(contestants, key=lambda x: x['f'])



def train():
    """Main training function for the genetic algorithm."""
    stats = load_json(STATS_FILE)
    if not stats:
        return

    population  = load_json(POPULATION_FILE)
    current_idx = load_json(CURRENT_INDEX_FILE)

    if not population:
        seed_weights = load_json(SHARED_WEIGHTS_PATH) or random_weights()
        population = [{'w': random_weights(), 'f': 0.0} for _ in range(POPULATION_SIZE)]
        population[0]['w'] = seed_weights   # особина 0 = кращі відомі ваги
        current_idx = 0

    if current_idx is None:
        current_idx = 0

    fitness = calc_fitness(stats)
    population[current_idx]['f'] = fitness
    print(f"  📊 Individual {current_idx} fitness: {fitness:.2f}")

    all_evaluated = all(p['f'] > 0 for p in population)

    if all_evaluated:
        population.sort(key=lambda x: x['f'], reverse=True)

        best_local = load_json(BEST_FILE)
        best_fitness = best_local.get('f', 0) if isinstance(best_local, dict) else 0

        if population[0]['f'] > best_fitness:
            print(f"  🎉 New record! Fitness: {population[0]['f']:.2f} (was {best_fitness:.2f})")
            best_entry = {'w': population[0]['w'], 'f': population[0]['f']}
            save_json(BEST_FILE, best_entry)             # локальний бекап
            save_json(SHARED_WEIGHTS_PATH, population[0]['w'])  # ← в shared!
        else:
            print(f"  — No improvement (best: {best_fitness:.2f})")

        new_pop = [deepcopy(p) for p in population[:TOP_KEEP]]

        while len(new_pop) < POPULATION_SIZE:
            p1 = tournament_select(population)
            p2 = tournament_select(population)
            child = {'w': mutate(crossover(p1['w'], p2['w'])), 'f': 0.0}
            new_pop.append(child)

        population  = new_pop
        current_idx = 0

    else:
        current_idx += 1
        while current_idx < len(population) and population[current_idx]['f'] > 0:
            current_idx += 1
        if current_idx >= len(population):
            current_idx = 0

    save_json(POPULATION_FILE,    population)
    save_json(CURRENT_INDEX_FILE, current_idx)
    save_json(WEIGHTS_FILE,       population[current_idx]['w'])


if __name__ == "__main__":
    train()
