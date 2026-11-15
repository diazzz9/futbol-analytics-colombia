"""Genera docs/simulacion.png: probabilidad de llegar a la final y de ser campeón según la simulación."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOCUS = "Santa Fe"
INK, MUTED, GRID, RED, GRAY, LIGHT = "#1f1f1f", "#6b6b6b", "#e6e6e6", "#c8102e", "#5f6368", "#c9ccd1"


def main():
    d = pd.read_csv(ROOT / "dashboard" / "data" / "simulacion.csv").sort_values("p_campeon")
    fig, ax = plt.subplots(figsize=(8, 4.6), dpi=160)
    y = range(len(d))
    ax.barh([i + 0.2 for i in y], d.p_campeon, height=0.36, color=[RED if e == FOCUS else GRAY for e in d.equipo])
    ax.barh([i - 0.2 for i in y], d.p_final, height=0.36, color=LIGHT)
    for i, r in zip(y, d.itertuples()):
        ax.text(r.p_campeon + 0.7, i + 0.2, f"{r.p_campeon:.1f} %".replace(".", ","), va="center", fontsize=8.5,
                color=INK, fontweight="bold")
        ax.text(r.p_final + 0.7, i - 0.2, f"{r.p_final:.1f} %".replace(".", ","), va="center", fontsize=8.5, color=MUTED)
    labels = [("★ " if r.cabeza == "sí" else "") + f"{r.equipo} · {r.grupo}" for r in d.itertuples()]
    ax.set_yticks(list(y), labels, fontsize=9.5, color=INK)
    for tick, e in zip(ax.get_yticklabels(), d.equipo):
        tick.set_fontweight("bold" if e == FOCUS else "normal")
    ax.set_xlim(0, d.p_final.max() * 1.14)
    ax.xaxis.set_visible(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    n = f"{int(d.simulaciones.iloc[0]):,}".replace(",", ".")
    fig.text(0.02, 0.95, "Quién llega a la final y quién sale campeón", fontsize=13, color=INK, fontweight="bold")
    fig.text(0.02, 0.895, f"Barra oscura: sale campeón · barra clara: llega a la final · % de {n} simulaciones · "
                          "★ cabeza de serie con punto invisible", fontsize=8.5, color=MUTED)
    fig.subplots_adjust(left=0.2, right=0.98, top=0.86, bottom=0.03)
    fig.savefig(ROOT / "docs" / "simulacion.png", facecolor="white")


if __name__ == "__main__":
    main()
