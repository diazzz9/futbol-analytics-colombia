"""Genera los CSV agregados que alimentan el dashboard (dashboard/data/) para todos los equipos del torneo actual."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "data"
SHORT = {"Independiente Santa Fe": "Santa Fe", "Independiente Medellín": "Medellín", "Atlético Nacional": "Nacional",
         "Atlético Junior": "Junior", "Atlético Bucaramanga": "Bucaramanga", "Internacional de Bogotá": "Inter Bogotá",
         "Jaguares de Córdoba": "Jaguares", "Boyacá Chicó FC": "Chicó", "Deportivo Pereira": "Pereira",
         "Deportivo Pasto": "Pasto", "Deportivo Cali": "Cali", "Deportes Tolima": "Tolima", "América de Cali": "América",
         "Cúcuta Deportivo": "Cúcuta", "Fortaleza CEIF": "Fortaleza", "Llaneros FC": "Llaneros", "Alianza FC": "Alianza"}
TRAMOS = ["1-15", "16-30", "31-45", "46-60", "61-75", "76-90"]


def label(season, tournament):
    return season.astype(str) + " " + tournament.str[0].map({"A": "I", "C": "II"})


def team_rows(m: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo y partido."""
    cols = ["possession", "shots"]
    home = m.assign(team_id=m.home_id, rival_id=m.away_id, cond="local", gf=m.home_goals, gc=m.away_goals,
                    **{c: m[f"home_{c}"] for c in cols})
    away = m.assign(team_id=m.away_id, rival_id=m.home_id, cond="visitante", gf=m.away_goals, gc=m.home_goals,
                    **{c: m[f"away_{c}"] for c in cols})
    tm = pd.concat([home, away]).sort_values("kickoff")
    tm["pts"] = (tm.gf > tm.gc) * 3 + (tm.gf == tm.gc) * 1
    tm["res"] = tm.pts.map({3: "G", 1: "E", 0: "P"})
    tm["torneo"] = label(tm.season, tm.tournament)
    return tm


def standings(tm: pd.DataFrame) -> pd.DataFrame:
    reg = tm[tm.phase == "Todos contra todos"]
    t = reg.groupby(["season", "tournament", "torneo", "team_id"]).agg(
        pj=("pts", "size"), pg=("res", lambda s: (s == "G").sum()), pe=("res", lambda s: (s == "E").sum()),
        pp=("res", lambda s: (s == "P").sum()), gf=("gf", "sum"), gc=("gc", "sum"), pts=("pts", "sum")).reset_index()
    t["dg"] = t.gf - t.gc
    t = t.sort_values(["season", "tournament", "pts", "dg", "gf"], ascending=[True, True, False, False, False])
    t["pos"] = t.groupby(["season", "tournament"]).cumcount() + 1
    return t


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    teams = pd.read_csv(P / "teams.csv")
    name = teams.set_index("team_id").name.map(lambda n: SHORT.get(n, n))
    m = pd.read_csv(P / "matches.csv", parse_dates=["kickoff"])
    ev = pd.read_csv(P / "events.csv")
    tm = team_rows(m)
    tm["equipo"] = tm.team_id.map(name)
    st = standings(tm)
    last = m.sort_values("kickoff").iloc[-1]
    season, tournament = int(last.season), last.tournament

    table = st[(st.season == season) & (st.tournament == tournament)].copy()
    table["equipo"] = table.team_id.map(name)
    table[["pos", "equipo", "pj", "pg", "pe", "pp", "gf", "gc", "dg", "pts"]].to_csv(OUT / "tabla_actual.csv", index=False)
    current = list(table.team_id)
    tm = tm[tm.team_id.isin(current)]

    tor = tm.groupby(["equipo", "torneo"], sort=False).agg(pj=("pts", "size"), pts=("pts", "sum"), gf=("gf", "sum"),
                                                           gc=("gc", "sum"), posesion=("possession", "mean"),
                                                           tiros=("shots", "mean")).reset_index()
    tor["ppp"] = (tor.pts / tor.pj).round(2)
    pos = st.assign(equipo=st.team_id.map(name))[["equipo", "torneo", "pos"]]
    tor = tor.merge(pos, on=["equipo", "torneo"], how="left")
    liga = team_rows(m).groupby("torneo").pts.mean().round(2)
    tor["ppp_liga"] = tor.torneo.map(liga)
    tor = tor.sort_values(["equipo", "torneo"]).round({"posesion": 1, "tiros": 1})
    tor.to_csv(OUT / "torneos_equipo.csv", index=False)

    goals = ev[(ev.kind == "gol") & ev.minute.notna()].merge(m[["match_id", "season", "home_id", "away_id"]], on="match_id")
    goals = goals[goals.season == season]
    goals["tramo"] = pd.cut(goals.minute.clip(upper=90), [0, 15, 30, 45, 60, 75, 90], labels=TRAMOS, include_lowest=True)
    rows = []
    for t in current:
        g = goals[(goals.home_id == t) | (goals.away_id == t)]
        favor = g[g.team_id == t].groupby("tramo", observed=False).size()
        contra = g[g.team_id != t].groupby("tramo", observed=False).size()
        rows += [{"equipo": name[t], "tramo": k, "a_favor": int(favor[k]), "en_contra": int(contra[k])} for k in TRAMOS]
    pd.DataFrame(rows).to_csv(OUT / "goles_tramos.csv", index=False)

    sc = ev[(ev.kind == "gol") & ~ev.own_goal & ev.team_id.isin(current) & ev.player.notna()]
    top = sc.groupby(["team_id", "player"]).agg(goles=("event_id", "size"), penales=("penalty", "sum")).reset_index()
    top = top.sort_values(["team_id", "goles", "player"], ascending=[True, False, True]).groupby("team_id").head(8)
    top.insert(0, "equipo", top.team_id.map(name))
    top.drop(columns="team_id").rename(columns={"player": "jugador"}).to_csv(OUT / "goleadores_equipo.csv", index=False)

    fz = pd.read_csv(P / "team_strengths.csv")
    fz["equipo"] = fz.team_id.map(name)
    fz[["equipo", "attack", "defense"]].rename(columns={"attack": "ataque", "defense": "defensa"}).to_csv(OUT / "fuerzas.csv", index=False)

    pr = pd.read_csv(P / "predictions.csv")
    home = pd.DataFrame({"equipo": pr.home_id.map(name), "rival": pr.away_id.map(name), "cond": "local",
                         "gana": pr.p_home, "empata": pr.p_draw, "pierde": pr.p_away, "marcador_probable": pr.most_likely_score})
    away = pd.DataFrame({"equipo": pr.away_id.map(name), "rival": pr.home_id.map(name), "cond": "visitante",
                         "gana": pr.p_away, "empata": pr.p_draw, "pierde": pr.p_home,
                         "marcador_probable": pr.most_likely_score.str.split("-").map(lambda s: f"{s[1]}-{s[0]}")})
    pred = pd.concat([home, away])
    for c in ("gana", "empata", "pierde"):
        pred[c] = (pred[c] * 100).round(1)
    pred.sort_values(["equipo", "cond", "gana"], ascending=[True, True, False]).to_csv(OUT / "predicciones_equipo.csv", index=False)

    met = pd.read_csv(P / "model_metrics.csv")
    met["accuracy"] = (met.accuracy * 100).round(1)
    met.rename(columns={"accuracy": "acierto_pct"}).round(3).to_csv(OUT / "modelo_metricas.csv", index=False)

    sim = pd.read_csv(P / "simulation.csv")
    sim["equipo"] = sim.team_id.map(name)
    sim["cabeza"] = sim.cabeza_de_serie.map({True: "sí", False: "no"})
    for c in ("p_final", "p_campeon"):
        sim[c] = (sim[c] * 100).round(1)
    sim.sort_values("p_campeon", ascending=False)[
        ["equipo", "grupo", "cabeza", "puesto_fase1", "pts_esperados", "p_final", "p_campeon", "partidos_jugados",
         "simulaciones"]].to_csv(OUT / "simulacion.csv", index=False)

    leader = table.iloc[0]
    res = []
    for row in table.itertuples():
        mine = tm[tm.team_id == row.team_id]
        cur = mine[(mine.season == season) & (mine.tournament == tournament)]
        hist = tor[tor.equipo == row.equipo]
        prev = hist.iloc[-2] if len(hist) > 1 else None
        ult = mine.iloc[-1]
        ppp = round(row.pts / row.pj, 2)
        res.append({
            "equipo": row.equipo, "torneo": f"{tournament} {season}", "pos": row.pos, "pts": row.pts, "pj": row.pj,
            "gf": row.gf, "gc": row.gc, "dg": row.dg, "ppp": ppp,
            "ppp_cambio": round(ppp - prev.ppp, 2) if prev is not None else None,
            "torneo_previo": prev.torneo if prev is not None else None,
            "lider": leader.equipo, "brecha": int(leader.pts - row.pts), "racha5": "".join(cur.res.tail(5)),
            "pts5": int(cur.pts.tail(5).sum()), "ultimo_rival": name[ult.rival_id],
            "ultimo_marcador": f"{ult.gf}-{ult.gc}", "ultimo_cond": ult.cond,
            "ultimo_fecha": ult.kickoff.strftime("%Y-%m-%d"), "partidos_total": len(m),
            "hasta": m.kickoff.max().strftime("%Y-%m-%d"),
        })
    pd.DataFrame(res).to_csv(OUT / "resumen.csv", index=False)
    (OUT / "partidos_equipo.csv").unlink(missing_ok=True)
    for f in sorted(OUT.glob("*.csv")):
        print(f.name, f.stat().st_size, len(pd.read_csv(f)))


if __name__ == "__main__":
    main()
