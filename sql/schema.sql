-- Esquema de futbol-analytics-colombia (PostgreSQL 14+)
DROP VIEW IF EXISTS v_standings;
DROP VIEW IF EXISTS v_team_matches;
DROP TABLE IF EXISTS simulation;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS matches;
DROP TABLE IF EXISTS teams;

CREATE TABLE teams (
    team_id  INTEGER PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE,
    abbr     TEXT NOT NULL
);

CREATE TABLE matches (
    match_id              INTEGER PRIMARY KEY,
    kickoff               TIMESTAMP NOT NULL,          -- hora de Bogotá
    season                INTEGER NOT NULL,
    tournament            TEXT NOT NULL CHECK (tournament IN ('Apertura', 'Clausura')),
    phase                 TEXT NOT NULL,
    home_id               INTEGER NOT NULL REFERENCES teams (team_id),
    away_id               INTEGER NOT NULL REFERENCES teams (team_id),
    home_goals            INTEGER NOT NULL CHECK (home_goals >= 0),
    away_goals            INTEGER NOT NULL CHECK (away_goals >= 0),
    result                CHAR(1) NOT NULL CHECK (result IN ('H', 'D', 'A')),
    status                TEXT NOT NULL,
    venue                 TEXT,
    city                  TEXT,
    attendance            INTEGER,
    note                  TEXT,
    home_possession       NUMERIC(4, 1),
    home_shots            INTEGER,
    home_shots_on_target  INTEGER,
    home_corners          INTEGER,
    home_fouls            INTEGER,
    home_yellow           INTEGER NOT NULL DEFAULT 0,
    home_red              INTEGER NOT NULL DEFAULT 0,
    away_possession       NUMERIC(4, 1),
    away_shots            INTEGER,
    away_shots_on_target  INTEGER,
    away_corners          INTEGER,
    away_fouls            INTEGER,
    away_yellow           INTEGER NOT NULL DEFAULT 0,
    away_red              INTEGER NOT NULL DEFAULT 0,
    CHECK (home_id <> away_id)
);

CREATE TABLE events (
    event_id    INTEGER PRIMARY KEY,
    match_id    INTEGER NOT NULL REFERENCES matches (match_id),
    team_id     INTEGER REFERENCES teams (team_id),
    minute      INTEGER,
    added_time  INTEGER NOT NULL DEFAULT 0,
    kind        TEXT NOT NULL CHECK (kind IN ('gol', 'amarilla', 'roja')),
    detail      TEXT,
    penalty     BOOLEAN NOT NULL DEFAULT FALSE,
    own_goal    BOOLEAN NOT NULL DEFAULT FALSE,
    player      TEXT
);

CREATE TABLE predictions (
    home_id   INTEGER NOT NULL REFERENCES teams (team_id),
    away_id   INTEGER NOT NULL REFERENCES teams (team_id),
    p_home    NUMERIC(5, 4) NOT NULL,
    p_draw    NUMERIC(5, 4) NOT NULL,
    p_away    NUMERIC(5, 4) NOT NULL,
    exp_home_goals NUMERIC(4, 2) NOT NULL,
    exp_away_goals NUMERIC(4, 2) NOT NULL,
    PRIMARY KEY (home_id, away_id)
);

CREATE TABLE simulation (
    team_id          INTEGER PRIMARY KEY REFERENCES teams (team_id),
    grupo            CHAR(1) NOT NULL,
    cabeza_de_serie  BOOLEAN NOT NULL,
    puesto_fase1     INTEGER NOT NULL,
    pts_esperados    NUMERIC(4, 2) NOT NULL,
    p_final          NUMERIC(5, 4) NOT NULL,
    p_campeon        NUMERIC(5, 4) NOT NULL,
    partidos_jugados INTEGER NOT NULL,
    simulaciones     INTEGER NOT NULL
);

CREATE INDEX idx_matches_season ON matches (season, tournament, phase);
CREATE INDEX idx_matches_home ON matches (home_id);
CREATE INDEX idx_matches_away ON matches (away_id);
CREATE INDEX idx_events_match ON events (match_id);
CREATE INDEX idx_events_player ON events (player);

-- Una fila por equipo y partido: evita duplicar la lógica local/visitante en cada consulta
CREATE VIEW v_team_matches AS
SELECT match_id, kickoff, season, tournament, phase, home_id AS team_id, away_id AS rival_id, 'L' AS venue_side,
       home_goals AS gf, away_goals AS ga,
       CASE result WHEN 'H' THEN 3 WHEN 'D' THEN 1 ELSE 0 END AS points,
       home_possession AS possession, home_shots AS shots, home_shots_on_target AS shots_on_target
FROM matches
UNION ALL
SELECT match_id, kickoff, season, tournament, phase, away_id, home_id, 'V',
       away_goals, home_goals,
       CASE result WHEN 'A' THEN 3 WHEN 'D' THEN 1 ELSE 0 END,
       away_possession, away_shots, away_shots_on_target
FROM matches;

-- Tabla de posiciones de la fase todos contra todos de cada torneo
CREATE VIEW v_standings AS
SELECT tm.season, tm.tournament, t.team_id, t.name,
       COUNT(*) AS pj,
       SUM(CASE WHEN tm.points = 3 THEN 1 ELSE 0 END) AS pg,
       SUM(CASE WHEN tm.points = 1 THEN 1 ELSE 0 END) AS pe,
       SUM(CASE WHEN tm.points = 0 THEN 1 ELSE 0 END) AS pp,
       SUM(tm.gf) AS gf, SUM(tm.ga) AS gc, SUM(tm.gf) - SUM(tm.ga) AS dg,
       SUM(tm.points) AS pts
FROM v_team_matches tm
JOIN teams t ON t.team_id = tm.team_id
WHERE tm.phase = 'Todos contra todos'
GROUP BY tm.season, tm.tournament, t.team_id, t.name;
