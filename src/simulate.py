"""Simulación Monte Carlo de los cuadrangulares y la final con el modelo de Poisson.

Reglas: dos grupos de cuatro a ida y vuelta; el primero de cada grupo va a la final. Los cabezas de serie
tienen punto invisible (ganan cualquier empate en puntos); después deciden diferencia de gol, goles a favor
y goles de visitante. La final es a ida y vuelta y, si hay empate global, se define por penales (50/50).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from model import PoissonModel, load_matches

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "data" / "config" / "cuadrangulares.json"
N_SIMS = 20_000


def simulate_group(ids, seeds, lam, played, rng, n):
    """Devuelve (índice del ganador por simulación, puntos por simulación)."""
    k = len(ids)
    pts, gd, gf, agf = (np.zeros((n, k)) for _ in range(4))
    for i in range(k):
        for j in range(k):
            if i == j:
                continue
            done = played.get((ids[i], ids[j]))
            if done is not None:
                hg, ag = np.full(n, done[0]), np.full(n, done[1])
            else:
                lh, la = lam[(ids[i], ids[j])]
                hg, ag = rng.poisson(lh, n), rng.poisson(la, n)
            pts[:, i] += 3 * (hg > ag) + (hg == ag)
            pts[:, j] += 3 * (ag > hg) + (hg == ag)
            gd[:, i] += hg - ag
            gd[:, j] += ag - hg
            gf[:, i] += hg
            gf[:, j] += ag
            agf[:, j] += ag
    seed = np.array([t in seeds for t in ids], float)
    key = pts * 1e8 + seed * 1e7 + (gd + 50) * 1e5 + gf * 1e3 + agf * 10 + rng.random((n, k))
    return key.argmax(1), pts


def simulate_final(wa, wb, ids_a, ids_b, rank, lam, rng, n):
    """Ida y vuelta; cierra de local el mejor ubicado en el todos contra todos."""
    champ = np.empty(n, dtype=int)
    for i, a in enumerate(ids_a):
        for j, b in enumerate(ids_b):
            mask = (wa == i) & (wb == j)
            m = int(mask.sum())
            if not m:
                continue
            first, second = (b, a) if rank[a] < rank[b] else (a, b)   # 'second' es local en la vuelta
            l1h, l1a = lam[(first, second)]
            l2h, l2a = lam[(second, first)]
            g_first = rng.poisson(l1h, m) + rng.poisson(l2a, m)
            g_second = rng.poisson(l1a, m) + rng.poisson(l2h, m)
            pens = rng.random(m) < 0.5
            champ[mask] = np.where((g_first > g_second) | ((g_first == g_second) & pens), first, second)
    return champ


def run(n=N_SIMS, seed=42):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    teams = pd.read_csv(PROCESSED / "teams.csv")
    tid = teams.set_index("name").team_id
    df = load_matches()
    model = PoissonModel().fit(df)
    cur = df[(df.season == cfg["season"]) & (df.tournament == cfg["tournament"])]

    reg = cur[cur.phase == "Todos contra todos"]
    table = {}
    for r in reg.itertuples():
        for t, g, c in ((r.home_id, r.home_goals, r.away_goals), (r.away_id, r.away_goals, r.home_goals)):
            p, d, f = table.get(t, (0, 0, 0))
            table[t] = (p + 3 * (g > c) + (g == c), d + g - c, f + g)
    order = sorted(table, key=lambda t: table[t], reverse=True)
    rank = {t: i + 1 for i, t in enumerate(order)}

    quad = cur[cur.phase == "Cuadrangulares"]
    played = {(r.home_id, r.away_id): (r.home_goals, r.away_goals) for r in quad.itertuples()}
    groups = {g: [int(tid[name]) for name in names] for g, names in cfg["groups"].items()}
    seeds = {int(tid[name]) for name in cfg["seeds"]}
    all_ids = [t for ids in groups.values() for t in ids]
    lam = {(h, a): model.expected_goals(h, a) for h in all_ids for a in all_ids if h != a}

    rng = np.random.default_rng(seed)
    winners, rows = {}, []
    for g, ids in groups.items():
        win, pts = simulate_group(ids, seeds, lam, played, rng, n)
        winners[g] = win
        for i, t in enumerate(ids):
            rows.append({"team_id": t, "grupo": g, "cabeza_de_serie": t in seeds, "puesto_fase1": rank[t],
                         "pts_esperados": round(float(pts[:, i].mean()), 2), "p_final": float((win == i).mean())})
    ga, gb = list(groups)
    champ = simulate_final(winners[ga], winners[gb], groups[ga], groups[gb], rank, lam, rng, n)
    out = pd.DataFrame(rows)
    out["p_campeon"] = out.team_id.map(lambda t: float((champ == t).mean()))
    out["partidos_jugados"] = len(quad)
    out["simulaciones"] = n
    return out.merge(teams[["team_id", "name"]], on="team_id")


def main():
    out = run()
    out.round(4).to_csv(PROCESSED / "simulation.csv", index=False)
    print(out[["grupo", "name", "puesto_fase1", "pts_esperados", "p_final", "p_campeon"]].round(3).to_string(index=False))
    print("sumas:", out.groupby("grupo").p_final.sum().round(3).to_dict(), "campeón:", round(out.p_campeon.sum(), 3))


if __name__ == "__main__":
    main()
