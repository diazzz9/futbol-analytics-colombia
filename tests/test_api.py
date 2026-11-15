"""Pruebas de humo de la API contra la base cargada (requiere DATABASE_URL)."""
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)
SANTA_FE = 5488


def test_health():
    assert client.get("/health").json()["matches"] > 2000


def test_standings_points_are_consistent():
    table = client.get("/standings", params={"season": 2026, "tournament": "Clausura"}).json()
    assert len(table) == 20
    assert all(r["pts"] == 3 * r["pg"] + r["pe"] and r["pj"] == r["pg"] + r["pe"] + r["pp"] for r in table)
    assert sum(r["gf"] for r in table) == sum(r["gc"] for r in table)


def test_team_endpoints():
    assert client.get("/teams", params={"q": "santa"}).json()[0]["team_id"] == SANTA_FE
    assert len(client.get(f"/teams/{SANTA_FE}/matches", params={"limit": 5}).json()) == 5
    assert client.get(f"/teams/{SANTA_FE}/summary").json()["tournaments"]
    assert client.get("/teams/1/matches").status_code == 404


def test_predict_probabilities_sum_to_one():
    p = client.get("/predict", params={"home_id": SANTA_FE, "away_id": 5484}).json()
    assert abs(float(p["p_home"]) + float(p["p_draw"]) + float(p["p_away"]) - 1) < 1e-3


def test_scorers():
    top = client.get("/scorers", params={"season": 2025, "limit": 3}).json()
    assert len(top) == 3 and top[0]["goals"] >= top[1]["goals"]


def test_simulation_is_a_probability_distribution():
    sim = client.get("/simulation").json()
    assert len(sim) == 8
    assert abs(sum(float(r["p_campeon"]) for r in sim) - 1) < 0.01
    for grupo in ("A", "B"):
        assert abs(sum(float(r["p_final"]) for r in sim if r["grupo"] == grupo) - 1) < 0.01
