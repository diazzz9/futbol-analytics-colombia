"""API de solo lectura sobre la base de datos de la liga colombiana."""
import os

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg2://futbol:futbol@localhost:5432/futbol")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
app = FastAPI(title="Fútbol Analytics Colombia", version="1.0.0",
              description="Resultados, estadísticas y predicciones de la Liga BetPlay (2022-2026).")


def db():
    with engine.connect() as conn:
        yield conn


def rows(conn, sql: str, **params) -> list[dict]:
    return [dict(r._mapping) for r in conn.execute(text(sql), params)]


def team_or_404(conn, team_id: int) -> dict:
    found = rows(conn, "SELECT team_id, name, abbr FROM teams WHERE team_id = :id", id=team_id)
    if not found:
        raise HTTPException(404, f"No existe el equipo {team_id}")
    return found[0]


@app.get("/health")
def health(conn=Depends(db)):
    return rows(conn, "SELECT COUNT(*) AS matches, MAX(kickoff) AS last_kickoff FROM matches")[0]


@app.get("/teams")
def teams(q: str | None = Query(None, description="Filtro por nombre"), conn=Depends(db)):
    return rows(conn, "SELECT team_id, name, abbr FROM teams WHERE LOWER(name) LIKE :q ORDER BY name",
                q=f"%{(q or '').lower()}%")


@app.get("/standings")
def standings(season: int = 2026, tournament: str = Query("Clausura", pattern="^(Apertura|Clausura)$"),
              conn=Depends(db)):
    table = rows(conn, """
        SELECT team_id, name, pj, pg, pe, pp, gf, gc, dg, pts FROM v_standings
        WHERE season = :season AND tournament = :tournament
        ORDER BY pts DESC, dg DESC, gf DESC, name""", season=season, tournament=tournament)
    if not table:
        raise HTTPException(404, "No hay partidos para ese torneo")
    return [{"pos": i + 1, **r} for i, r in enumerate(table)]


@app.get("/teams/{team_id}/matches")
def team_matches(team_id: int, season: int | None = None, limit: int = Query(20, ge=1, le=200), conn=Depends(db)):
    team_or_404(conn, team_id)
    return rows(conn, """
        SELECT m.match_id, m.kickoff, m.season, m.tournament, m.phase, h.name AS home, a.name AS away,
               m.home_goals, m.away_goals, m.venue, m.attendance
        FROM matches m JOIN teams h ON h.team_id = m.home_id JOIN teams a ON a.team_id = m.away_id
        WHERE (m.home_id = :id OR m.away_id = :id) AND (:season IS NULL OR m.season = :season)
        ORDER BY m.kickoff DESC LIMIT :limit""", id=team_id, season=season, limit=limit)


@app.get("/teams/{team_id}/summary")
def team_summary(team_id: int, conn=Depends(db)):
    team = team_or_404(conn, team_id)
    seasons = rows(conn, """
        SELECT season, tournament, COUNT(*) AS pj, SUM(points) AS pts, SUM(gf) AS gf, SUM(ga) AS gc,
               ROUND(AVG(possession), 1) AS possession, ROUND(AVG(shots), 1) AS shots
        FROM v_team_matches WHERE team_id = :id
        GROUP BY season, tournament ORDER BY season, tournament""", id=team_id)
    return {**team, "tournaments": seasons}


@app.get("/scorers")
def scorers(season: int | None = None, team_id: int | None = None, limit: int = Query(15, ge=1, le=100),
            conn=Depends(db)):
    return rows(conn, """
        SELECT e.player, t.name AS team, COUNT(*) AS goals,
               SUM(CASE WHEN e.penalty THEN 1 ELSE 0 END) AS penalties
        FROM events e JOIN matches m ON m.match_id = e.match_id JOIN teams t ON t.team_id = e.team_id
        WHERE e.kind = 'gol' AND NOT e.own_goal AND e.player IS NOT NULL
          AND (:season IS NULL OR m.season = :season) AND (:team_id IS NULL OR e.team_id = :team_id)
        GROUP BY e.player, t.name ORDER BY goals DESC, e.player LIMIT :limit""",
                season=season, team_id=team_id, limit=limit)


@app.get("/predict")
def predict(home_id: int, away_id: int, conn=Depends(db)):
    found = rows(conn, """
        SELECT h.name AS home, a.name AS away, p.p_home, p.p_draw, p.p_away, p.exp_home_goals, p.exp_away_goals
        FROM predictions p JOIN teams h ON h.team_id = p.home_id JOIN teams a ON a.team_id = p.away_id
        WHERE p.home_id = :h AND p.away_id = :a""", h=home_id, a=away_id)
    if not found:
        raise HTTPException(404, "Solo hay predicciones entre equipos del torneo actual")
    return found[0]


@app.get("/simulation")
def simulation(conn=Depends(db)):
    """Probabilidad de llegar a la final y de ser campeón para los equipos en cuadrangulares."""
    return rows(conn, """
        SELECT t.name AS team, s.grupo, s.cabeza_de_serie, s.puesto_fase1, s.pts_esperados, s.p_final, s.p_campeon,
               s.partidos_jugados, s.simulaciones
        FROM simulation s JOIN teams t ON t.team_id = s.team_id
        ORDER BY s.p_campeon DESC""")


@app.get("/")
def root():
    return {"proyecto": "Fútbol Analytics Colombia", "documentacion": "/docs",
            "ejemplos": ["/standings", "/simulation", "/scorers?season=2026", "/predict?home_id=5488&away_id=5484"]}
