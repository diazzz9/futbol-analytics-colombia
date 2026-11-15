"""ETL: convierte el JSON crudo de ESPN en tres tablas limpias (teams, matches, events) en data/processed/."""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "liga_betplay_espn_2022_2026.json"
OUT = ROOT / "data" / "processed"

STAT_MAP = {
    "possessionPct": "possession",
    "totalShots": "shots",
    "shotsOnTarget": "shots_on_target",
    "wonCorners": "corners",
    "foulsCommitted": "fouls",
}
PHASES = {"semifinals": "Cuadrangulares", "finals": "Final", "quarterfinals": "Cuartos de final"}


def parse_stage(slug: str, month: int, year: int) -> tuple[str, str]:
    """Normaliza los slugs inconsistentes de ESPN a (torneo, fase)."""
    last = slug.split("---")[-1]
    tournament = "Apertura" if month <= 6 else "Clausura"
    if last in ("apertura", "clausura"):
        return last.capitalize(), "Todos contra todos"
    phase = PHASES[last]
    if year == 2026 and last == "semifinals":
        phase = "Semifinal"
    return tournament, phase


def parse_minute(clock: str) -> tuple[int | None, int]:
    m = re.match(r"(\d+)'(?:\+(\d+)')?", clock or "")
    return (int(m.group(1)), int(m.group(2) or 0)) if m else (None, 0)


def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build(raw_path: Path = RAW):
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    teams, matches, events = {}, [], []
    for m in raw:
        when = pd.Timestamp(m["date"]).tz_convert("America/Bogota")
        tournament, phase = parse_stage(m["stage"], when.month, when.year)
        home, away = m["home"], m["away"]
        for side in (home, away):
            teams[int(side["id"])] = {"team_id": int(side["id"]), "name": side["name"], "abbr": side["abbr"]}
        hg, ag = int(home["score"]), int(away["score"])
        note = m["note"] or ""
        row = {
            "match_id": int(m["id"]),
            "kickoff": when.strftime("%Y-%m-%d %H:%M"),
            "season": when.year,
            "tournament": tournament,
            "phase": phase,
            "home_id": int(home["id"]),
            "away_id": int(away["id"]),
            "home_goals": hg,
            "away_goals": ag,
            "result": "H" if hg > ag else "A" if ag > hg else "D",
            "status": {"STATUS_FULL_TIME": "final", "STATUS_FINAL_PEN": "penales", "STATUS_ABANDONED": "abandonado"}[m["status"]],
            "venue": m["venue"],
            "city": m["city"],
            "attendance": m["attendance"] or None,
            "note": None if note == "Colombian Primera A" else note,
        }
        for prefix, side in (("home", home), ("away", away)):
            for src, dst in STAT_MAP.items():
                row[f"{prefix}_{dst}"] = num(side["stats"].get(src))
            row[f"{prefix}_yellow"] = sum(e["yc"] for e in m["events"] if e["team"] == side["id"])
            row[f"{prefix}_red"] = sum(e["rc"] for e in m["events"] if e["team"] == side["id"])
        matches.append(row)
        for e in m["events"]:
            minute, added = parse_minute(e["clock"])
            kind = "gol" if e["goal"] else "roja" if e["rc"] else "amarilla"
            events.append({
                "match_id": int(m["id"]),
                "team_id": int(e["team"]) if e["team"] else None,
                "minute": minute,
                "added_time": added,
                "kind": kind,
                "detail": e["type"],
                "penalty": bool(e["pen"]),
                "own_goal": bool(e["og"]),
                "player": e["player"] or None,
            })

    teams_df = pd.DataFrame(sorted(teams.values(), key=lambda t: t["name"]))
    matches_df = pd.DataFrame(matches).drop_duplicates("match_id").sort_values(["kickoff", "match_id"]).reset_index(drop=True)
    # ESPN codifica las estadísticas faltantes como 0: posesión 0 y 0 tiros significa "sin dato", no un cero real
    stat_cols = list(STAT_MAP.values())
    for prefix in ("home", "away"):
        missing = (matches_df[f"{prefix}_possession"] == 0) & (matches_df[f"{prefix}_shots"] == 0)
        matches_df.loc[missing, [f"{prefix}_{c}" for c in stat_cols]] = None
    for a, b in (("home", "away"), ("away", "home")):
        fill = matches_df[f"{a}_possession"].isna() & matches_df[f"{b}_possession"].notna()
        matches_df.loc[fill, f"{a}_possession"] = (100 - matches_df.loc[fill, f"{b}_possession"]).round(1)
    events_df = pd.DataFrame(events)
    events_df.insert(0, "event_id", range(1, len(events_df) + 1))
    for col in ("attendance", "home_shots", "away_shots", "home_shots_on_target", "away_shots_on_target",
                "home_corners", "away_corners", "home_fouls", "away_fouls"):
        matches_df[col] = matches_df[col].astype("Int64")
    events_df["team_id"] = events_df["team_id"].astype("Int64")
    events_df["minute"] = events_df["minute"].astype("Int64")
    return teams_df, matches_df, events_df


def validate(teams, matches, events):
    """Chequeos de calidad: llaves únicas, integridad referencial y rangos."""
    assert matches["match_id"].is_unique
    assert set(matches["home_id"]) | set(matches["away_id"]) <= set(teams["team_id"])
    assert set(events["match_id"]) <= set(matches["match_id"])
    assert (matches["home_id"] != matches["away_id"]).all()
    poss = (matches["home_possession"] + matches["away_possession"]).dropna()
    assert poss.between(99, 101).all(), "posesión no suma 100"
    assert (matches["home_shots_on_target"].fillna(0) <= matches["home_shots"].fillna(0)).all()


def main():
    teams, matches, events = build(Path(sys.argv[1]) if len(sys.argv) > 1 else RAW)
    validate(teams, matches, events)
    OUT.mkdir(parents=True, exist_ok=True)
    teams.to_csv(OUT / "teams.csv", index=False)
    matches.to_csv(OUT / "matches.csv", index=False)
    events.to_csv(OUT / "events.csv", index=False)
    print(f"teams={len(teams)} matches={len(matches)} events={len(events)}")
    print(matches.groupby(["season", "tournament", "phase"]).size().to_string())


if __name__ == "__main__":
    main()
