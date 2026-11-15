"""Crea el esquema y carga los CSV procesados en PostgreSQL (o SQLite si DATABASE_URL apunta a un archivo)."""
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DEFAULT_URL = "postgresql+psycopg2://futbol:futbol@localhost:5432/futbol"


def get_engine():
    return create_engine(os.environ.get("DATABASE_URL", DEFAULT_URL))


def main():
    engine = get_engine()
    schema = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    statements = [s.strip() for s in schema.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        teams = pd.read_csv(PROCESSED / "teams.csv")
        matches = pd.read_csv(PROCESSED / "matches.csv", parse_dates=["kickoff"])
        events = pd.read_csv(PROCESSED / "events.csv")
        preds = pd.read_csv(PROCESSED / "predictions.csv").drop(columns=["most_likely_score"])
        sim = pd.read_csv(PROCESSED / "simulation.csv").drop(columns=["name"])
        tables = (("teams", teams), ("matches", matches), ("events", events), ("predictions", preds), ("simulation", sim))
        for name, df in tables:
            df.to_sql(name, conn, if_exists="append", index=False, chunksize=1000)
            print(f"{name}: {len(df)} filas")


if __name__ == "__main__":
    main()
