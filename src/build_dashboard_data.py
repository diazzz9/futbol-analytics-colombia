"""Genera los CSV agregados que alimentan el dashboard (dashboard/data/), con foco en un equipo."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "dashboard" / "data"
TEAM = "Independiente Santa Fe"
SHORT = {"Independiente Santa Fe": "Santa Fe", "Independiente Medellín": "Medellín", "Atlético Nacional": "Nacional",
         "Atlético Junior": "Junior", "Atlético Bucaramanga": "Bucaramanga", "Internacional de Bogotá": "Inter Bogotá",
         "Jaguares de Córdoba": "Jaguares", "Boyacá Chicó FC": "Chicó", "Deportivo Pereira": "Pereira",
         "Deportivo Pasto": "Pasto", "Deportivo Cali": "Cali", "Deportes Tolima": "Tolima", "América de Cali": "América",
         "Cúcuta Deportivo": "Cúcuta", "Fortaleza CEIF": "Fortaleza", "Llaneros FC": "Llaneros", "Alianza FC": "Alianza"}


def team_rows(m: pd.DataFrame) -> pd.DataFrame:
    """Una fila por equipo y partido."""
    cols = ["possession", "shots", "shots_on_target", "corners"]
    home = m.assign(team_id=m.home_id, rival_id=m.away_id, cond="Local", gf=m.home_goals, gc=m.away_goals,
                    **{c: m[f"home_{c}"] for c in cols})
    away = m.assign(team_id=m.away_id, rival_id=m.home_id, cond="Visitante", gf=m.away_goals, gc=m.home_goals,
                    **{c: m[f"away_{c}"] for c in cols})
    tm = pd.concat([home, away]).sort_values("kickoff")
    tm["pts"] = (tm.gf > tm.gc) * 3 + (tm.gf == tm.gc) * 1
    tm["res"] = tm.pts.map({3: "G", 1: "E", 0: "P"})
    return tm


def standings(tm: pd.DataFrame) -> pd.DataFrame:
    reg = tm[tm.phase == "Todos contra todos"]
    t = reg.groupby(["season", "tournament", "team_id"]).agg(
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
    tid = int(teams.loc[teams.name == TEAM, "team_id"].iloc[0])
    tm = team_rows(m)
    st = standings(tm)
    last = m.sort_values("kickoff").iloc[-1]
    season, tournament = int(last.season), last.tournament

    table = st[(st.season == season) & (st.tournament == tournament)].copy()
    table["equipo"] = table.team_id.map(name)
    table[["pos", "equipo", "pj", "pg", "pe", "pp", "gf", "gc", "dg", "pts"]].to_csv(OUT / "tabla_actual.csv", index=False)

    mine = tm[tm.team_id == tid].copy()
    mine["rival"] = mine.rival_id.map(name)
    mine["fecha"] = mine.kickoff.dt.strftime("%Y-%m-%d")
    mine["torneo"] = mine.season.astype(str) + " " + mine.tournament.str[0].map({"A": "I", "C": "II"})
    partidos = mine[["match_id", "fecha", "torneo", "phase", "cond", "rival", "gf", "gc", "res", "pts",
                     "possession", "shots", "shots_on_target", "corners"]].rename(
        columns={"phase": "fase", "possession": "posesion", "shots": "tiros", "shots_on_target": "tiros_arco"})
    partidos.to_csv(OUT / "partidos_equipo.csv", index=False)

    tor = mine.groupby("torneo", sort=False).agg(pj=("pts", "size"), pts=("pts", "sum"), gf=("gf", "sum"),
                                                 gc=("gc", "sum"), posesion=("possession", "mean"),
                                                 tiros=("shots", "mean")).reset_index()
    tor["ppp"] = (tor.pts / tor.pj).round(2)
    pos = st[st.team_id == tid].assign(torneo=lambda d: d.season.astype(str) + " " + d.tournament.str[0].map({"A": "I", "C": "II"}))
    tor = tor.merge(pos[["torneo", "pos"]], on="torneo", how="left")
    liga = tm.groupby(tm.season.astype(str) + " " + tm.tournament.str[0].map({"A": "I", "C": "II"})).pts.mean().round(2)
    tor["ppp_liga"] = tor.torneo.map(liga)
    tor.round({"posesion": 1, "tiros": 1}).to_csv(OUT / "torneos_equipo.csv", index=False)

    goals = ev[(ev.kind == "gol") & ev.minute.notna()].merge(m[["match_id", "season", "home_id", "away_id"]], on="match_id")
    g = goals[(goals.season == season) & ((goals.home_id == tid) | (goals.away_id == tid))].copy()
    g["tramo"] = pd.cut(g.minute.clip(upper=90), [0, 15, 30, 45, 60, 75, 90],
                        labels=["1-15", "16-30", "31-45", "46-60", "61-75", "76-90"], include_lowest=True)
    g["lado"] = (g.team_id == tid).map({True: "a_favor", False: "en_contra"})
    g.groupby(["tramo", "lado"], observed=False).size().unstack(fill_value=0).reset_index().to_csv(OUT / "goles_tramos.csv", index=False)

    sc = ev[(ev.kind == "gol") & ~ev.own_goal & (ev.team_id == tid) & ev.player.notna()]
    top = sc.groupby("player").agg(goles=("event_id", "size"), penales=("penalty", "sum")).reset_index()
    top = top.sort_values(["goles", "player"], ascending=[False, True]).head(8).rename(columns={"player": "jugador"})
    top.to_csv(OUT / "goleadores_equipo.csv", index=False)

    fz = pd.read_csv(P / "team_strengths.csv")
    fz["equipo"] = fz.team_id.map(name)
    fz[["equipo", "attack", "defense"]].rename(columns={"attack": "ataque", "defense": "defensa"}).to_csv(OUT / "fuerzas.csv", index=False)

    pr = pd.read_csv(P / "predictions.csv")
    home = pr[pr.home_id == tid].assign(rival=lambda d: d.away_id.map(name), cond="Local",
                                        gana=lambda d: d.p_home, empata=lambda d: d.p_draw, pierde=lambda d: d.p_away)
    away = pr[pr.away_id == tid].assign(rival=lambda d: d.home_id.map(name), cond="Visitante",
                                        gana=lambda d: d.p_away, empata=lambda d: d.p_draw, pierde=lambda d: d.p_home)
    pred = pd.concat([home, away])[["rival", "cond", "gana", "empata", "pierde", "most_likely_score"]]
    pred = pred.rename(columns={"most_likely_score": "marcador_probable"})
    for c in ("gana", "empata", "pierde"):
        pred[c] = (pred[c] * 100).round(1)
    pred.sort_values(["cond", "gana"], ascending=[True, False]).to_csv(OUT / "predicciones_equipo.csv", index=False)

    met = pd.read_csv(P / "model_metrics.csv")
    met["accuracy"] = (met.accuracy * 100).round(1)
    met.rename(columns={"accuracy": "acierto_pct"}).round(3).to_csv(OUT / "modelo_metricas.csv", index=False)

    cur = mine[(mine.season == season) & (mine.tournament == tournament)]
    row = table[table.team_id == tid].iloc[0]
    prev = tor.iloc[-2]
    ult = mine.iloc[-1]
    resumen = pd.DataFrame([{
        "torneo": f"{tournament} {season}", "pos": int(row.pos), "pts": int(row.pts), "pj": int(row.pj),
        "gf": int(row.gf), "gc": int(row.gc), "dg": int(row.dg), "ppp": round(row.pts / row.pj, 2),
        "ppp_previo": prev.ppp, "ppp_cambio": round(row.pts / row.pj - prev.ppp, 2), "torneo_previo": prev.torneo,
        "lider": table.iloc[0].equipo, "pts_lider": int(table.iloc[0].pts), "racha5": "".join(cur.res.tail(5)),
        "pts5": int(cur.pts.tail(5).sum()), "ultimo_rival": ult.rival, "ultimo_marcador": f"{ult.gf}-{ult.gc}",
        "ultimo_cond": ult.cond.lower(), "ultimo_fecha": ult.fecha, "partidos_total": len(m),
        "desde": m.kickoff.min().strftime("%Y-%m-%d"), "hasta": m.kickoff.max().strftime("%Y-%m-%d"),
    }])
    resumen.to_csv(OUT / "resumen.csv", index=False)
    print(resumen.T.to_string())
    for f in sorted(OUT.glob("*.csv")):
        print(f.name, f.stat().st_size)


if __name__ == "__main__":
    main()
