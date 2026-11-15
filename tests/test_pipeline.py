"""Pruebas del ETL y del modelo sobre los datos procesados."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import etl  # noqa: E402
from model import PoissonModel, load_matches  # noqa: E402


def test_stage_normalization():
    assert etl.parse_stage("apertura", 3, 2024) == ("Apertura", "Todos contra todos")
    assert etl.parse_stage("playoffs---semifinals", 11, 2023) == ("Clausura", "Cuadrangulares")
    assert etl.parse_stage("apertura---semifinals", 5, 2026) == ("Apertura", "Semifinal")
    assert etl.parse_stage("finals", 6, 2022) == ("Apertura", "Final")


def test_minute_parsing():
    assert etl.parse_minute("90'+4'") == (90, 4)
    assert etl.parse_minute("7'") == (7, 0)
    assert etl.parse_minute("") == (None, 0)


def test_processed_tables_are_consistent():
    m = pd.read_csv(ROOT / "data" / "processed" / "matches.csv")
    assert m.match_id.is_unique and len(m) > 2000
    assert ((m.home_goals > m.away_goals) == (m.result == "H")).all()
    possession = (m.home_possession + m.away_possession).dropna()
    assert possession.between(99, 101).all()


def test_model_probabilities_and_home_advantage():
    model = PoissonModel().fit(load_matches())
    p = model.predict(5488, 5484)
    assert abs(p["p_home"] + p["p_draw"] + p["p_away"] - 1) < 1e-9
    assert model.home_ > 0
    assert p["p_home"] > model.predict(5484, 5488)["p_away"]
