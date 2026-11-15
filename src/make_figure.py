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
    plt.close(fig)
    social_card(d)


def social_card(d):
    """Imagen 1200x628 para la vista previa del enlace en redes (docs/og.png)."""
    resumen = pd.read_csv(ROOT / "dashboard" / "data" / "resumen.csv")
    corte = "/".join(reversed(str(resumen.hasta.iloc[0]).split("-")))
    fig, ax = plt.subplots(figsize=(12, 6.28), dpi=100)
    fig.patch.set_facecolor("#fbfaf6")
    ax.set_facecolor("#fbfaf6")
    y = range(len(d))
    ax.barh(list(y), d.p_campeon, height=0.62, color=INK)
    for i, r in zip(y, d.itertuples()):
        ax.text(r.p_campeon + 0.5, i, f"{r.p_campeon:.1f} %".replace(".", ","), va="center", fontsize=17, color=INK,
                fontweight="bold")
    ax.set_yticks(list(y), [("★ " if r.cabeza == "sí" else "") + r.equipo for r in d.itertuples()], fontsize=17, color=INK)
    ax.set_xlim(0, d.p_campeon.max() * 1.18)
    ax.xaxis.set_visible(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, pad=12)
    n = f"{int(d.simulaciones.iloc[0]):,}".replace(",", ".")
    fig.text(0.04, 0.9, "¿Quién será campeón de la Liga BetPlay?", fontsize=30, color=INK, fontfamily="serif")
    fig.text(0.04, 0.825, f"Probabilidad de título en {n} simulaciones · datos al {corte} · ★ cabeza de serie",
             fontsize=14.5, color=MUTED)
    fig.subplots_adjust(left=0.24, right=0.97, top=0.76, bottom=0.05)
    fig.savefig(ROOT / "docs" / "og.png", facecolor=fig.get_facecolor())


if __name__ == "__main__":
    main()
