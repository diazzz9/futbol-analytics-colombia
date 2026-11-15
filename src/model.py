"""Modelo de predicción: Poisson con fuerzas de ataque/defensa por equipo, ventaja de local y decaimiento temporal.

Se compara contra dos líneas base (frecuencias históricas y Elo) con validación temporal walk-forward.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MAX_GOALS = 8


class PoissonModel:
    def __init__(self, half_life_days: float = 365.0, ridge: float = 1.0):
        self.half_life_days = half_life_days
        self.ridge = ridge

    def fit(self, df: pd.DataFrame, as_of: pd.Timestamp | None = None):
        as_of = as_of or df["kickoff"].max()
        self.teams_ = sorted(set(df["home_id"]) | set(df["away_id"]))
        idx = {t: i for i, t in enumerate(self.teams_)}
        n = len(self.teams_)
        h = df["home_id"].map(idx).to_numpy()
        a = df["away_id"].map(idx).to_numpy()
        hg = df["home_goals"].to_numpy(float)
        ag = df["away_goals"].to_numpy(float)
        age = (as_of - df["kickoff"]).dt.days.to_numpy(float)
        w = 0.5 ** (age / self.half_life_days)

        def loss(p):
            att, dfn, mu, home = p[:n], p[n:2 * n], p[-2], p[-1]
            lh = np.exp(mu + home + att[h] - dfn[a])
            la = np.exp(mu + att[a] - dfn[h])
            nll = -(w * (hg * np.log(lh) - lh + ag * np.log(la) - la)).sum()
            grad = np.zeros_like(p)
            rh, ra = w * (lh - hg), w * (la - ag)
            np.add.at(grad, h, rh)
            np.add.at(grad, a, ra)
            np.add.at(grad, n + a, -rh)
            np.add.at(grad, n + h, -ra)
            grad[-2] = rh.sum() + ra.sum()
            grad[-1] = rh.sum()
            grad[:2 * n] += 2 * self.ridge * p[:2 * n]
            return nll + self.ridge * (p[:2 * n] ** 2).sum(), grad

        x0 = np.zeros(2 * n + 2)
        res = minimize(loss, x0, jac=True, method="L-BFGS-B")
        self.att_ = dict(zip(self.teams_, res.x[:n]))
        self.def_ = dict(zip(self.teams_, res.x[n:2 * n]))
        self.mu_, self.home_ = res.x[-2], res.x[-1]
        return self

    def expected_goals(self, home_id: int, away_id: int) -> tuple[float, float]:
        ah, dh = self.att_.get(home_id, 0.0), self.def_.get(home_id, 0.0)
        aa, da = self.att_.get(away_id, 0.0), self.def_.get(away_id, 0.0)
        return float(np.exp(self.mu_ + self.home_ + ah - da)), float(np.exp(self.mu_ + aa - dh))

    def predict(self, home_id: int, away_id: int) -> dict:
        lh, la = self.expected_goals(home_id, away_id)
        grid = np.outer(poisson.pmf(range(MAX_GOALS + 1), lh), poisson.pmf(range(MAX_GOALS + 1), la))
        grid /= grid.sum()
        best = np.unravel_index(grid.argmax(), grid.shape)
        return {
            "p_home": float(np.tril(grid, -1).sum()),
            "p_draw": float(np.trace(grid)),
            "p_away": float(np.triu(grid, 1).sum()),
            "exp_home_goals": lh,
            "exp_away_goals": la,
            "most_likely_score": f"{best[0]}-{best[1]}",
        }


def elo_probs(train: pd.DataFrame, test: pd.DataFrame, k=20.0, home_adv=70.0):
    """Línea base Elo; el empate se modela con la frecuencia histórica repartida según la cercanía de fuerzas."""
    rating = {}
    draw_rate = (train["result"] == "D").mean()

    def expected(h, a):
        return 1 / (1 + 10 ** ((rating.get(a, 1500) - rating.get(h, 1500) - home_adv) / 400))

    def update(row):
        e = expected(row.home_id, row.away_id)
        s = {"H": 1.0, "D": 0.5, "A": 0.0}[row.result]
        rating[row.home_id] = rating.get(row.home_id, 1500) + k * (s - e)
        rating[row.away_id] = rating.get(row.away_id, 1500) - k * (s - e)

    for row in train.itertuples():
        update(row)
    out = []
    for row in test.itertuples():
        e = expected(row.home_id, row.away_id)
        d = draw_rate * (1 - abs(2 * e - 1))
        out.append([e * (1 - d), d, (1 - e) * (1 - d)])
        update(row)
    return np.array(out)


def score(probs: np.ndarray, results: pd.Series) -> dict:
    y = results.map({"H": 0, "D": 1, "A": 2}).to_numpy()
    onehot = np.eye(3)[y]
    p = np.clip(probs, 1e-9, 1)
    return {
        "accuracy": float((probs.argmax(1) == y).mean()),
        "log_loss": float(-np.log(p[np.arange(len(y)), y]).mean()),
        "brier": float(((probs - onehot) ** 2).sum(1).mean()),
    }


def evaluate(df: pd.DataFrame, test_from: str = "2025-07-01") -> pd.DataFrame:
    """Walk-forward: el modelo se reentrena cada mes solo con partidos anteriores a los que predice."""
    df = df.sort_values("kickoff").reset_index(drop=True)
    test = df[df["kickoff"] >= test_from]
    train0 = df[df["kickoff"] < test_from]
    rows = []
    for _, block in test.groupby(test["kickoff"].dt.to_period("M")):
        past = df[df["kickoff"] < block["kickoff"].min()]
        model = PoissonModel().fit(past, as_of=block["kickoff"].min())
        for r in block.itertuples():
            p = model.predict(r.home_id, r.away_id)
            rows.append([p["p_home"], p["p_draw"], p["p_away"]])
    freq = train0["result"].value_counts(normalize=True)[["H", "D", "A"]].to_numpy()
    table = {
        "Frecuencias históricas": score(np.tile(freq, (len(test), 1)), test["result"]),
        "Elo": score(elo_probs(train0, test), test["result"]),
        "Poisson (este modelo)": score(np.array(rows), test["result"]),
    }
    out = pd.DataFrame(table).T
    out.insert(0, "partidos", len(test))
    return out


def load_matches() -> pd.DataFrame:
    return pd.read_csv(PROCESSED / "matches.csv", parse_dates=["kickoff"])


def main():
    df = load_matches()
    metrics = evaluate(df)
    print(metrics.round(4).to_string())
    metrics.round(4).to_csv(PROCESSED / "model_metrics.csv", index_label="modelo")

    model = PoissonModel().fit(df)
    current = df[(df["season"] == df["season"].max())]
    current = current[current["tournament"] == current.sort_values("kickoff")["tournament"].iloc[-1]]
    ids = sorted(set(current["home_id"]) | set(current["away_id"]))
    preds = [{"home_id": h, "away_id": a, **model.predict(h, a)} for h in ids for a in ids if h != a]
    pd.DataFrame(preds).round(4).to_csv(PROCESSED / "predictions.csv", index=False)
    strengths = pd.DataFrame({"team_id": model.teams_,
                              "attack": [model.att_[t] for t in model.teams_],
                              "defense": [model.def_[t] for t in model.teams_]})
    strengths[strengths["team_id"].isin(ids)].round(4).to_csv(PROCESSED / "team_strengths.csv", index=False)
    print(f"ventaja de local = x{np.exp(model.home_):.2f} goles | predicciones = {len(preds)}")


if __name__ == "__main__":
    main()
