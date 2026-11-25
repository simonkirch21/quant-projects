"""Génère les figures et le tableau de résultats du README.

Lancement depuis la racine du projet :  python scripts/demo.py
"""

from pathlib import Path
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pricer import (  # noqa: E402
    bs_greeks, bs_price, geometric_asian_price, mc_asian, mc_european, mc_greeks,
)

FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)
P = dict(S=100.0, K=105.0, T=1.0, r=0.05, sigma=0.25, q=0.01)


def convergence_figure():
    exact = bs_price(**P)
    ns = np.unique(np.logspace(2, 6, 25).astype(int))
    res = [mc_european(**P, n_paths=int(n), seed=42) for n in ns]
    price = np.array([r.price for r in res])
    se = np.array([r.std_error for r in res])

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.fill_between(ns, price - 1.96 * se, price + 1.96 * se, alpha=0.25,
                    label="IC 95 % Monte Carlo")
    ax.plot(ns, price, marker="o", ms=3, label="Monte Carlo")
    ax.axhline(exact, color="black", ls="--", label=f"Black-Scholes = {exact:.4f}")
    ax.set_xscale("log")
    ax.set_xlabel("Nombre de trajectoires")
    ax.set_ylabel("Prix du call")
    ax.set_title("Convergence du Monte Carlo vers Black-Scholes")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "convergence.png", dpi=150)
    plt.close(fig)


def variance_reduction_figure():
    ns = np.unique(np.logspace(3, 6, 13).astype(int))
    methods = {
        "Simple": {},
        "Antithétique": {"antithetic": True},
        "Variable de contrôle": {"control_variate": True},
        "Les deux": {"antithetic": True, "control_variate": True},
    }
    fig, ax = plt.subplots(figsize=(8, 4.5))
    first_se = None
    for label, kw in methods.items():
        se = [mc_european(**P, n_paths=int(n), seed=42, **kw).std_error for n in ns]
        first_se = first_se or se[0]
        ax.loglog(ns, se, marker="o", ms=3, label=label)
    ax.loglog(ns, first_se * (ns[0] / ns) ** 0.5, ls=":", color="grey", label="pente -1/2")
    ax.set_xlabel("Nombre de trajectoires (coût égal)")
    ax.set_ylabel("Erreur type")
    ax.set_title("Réduction de variance")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "variance_reduction.png", dpi=150)
    plt.close(fig)


def results_table():
    n = 100_000
    exact = bs_price(**P)
    rows = []
    plain_se = None
    for label, kw in [
        ("Simple", {}),
        ("Antithétique", {"antithetic": True}),
        ("Variable de contrôle", {"control_variate": True}),
        ("Antithétique + contrôle", {"antithetic": True, "control_variate": True}),
    ]:
        r = mc_european(**P, n_paths=n, seed=42, **kw)
        plain_se = plain_se or r.std_error
        rows.append(f"| {label} | {r.price:.4f} | {r.std_error:.4f} | "
                    f"{r.price - exact:+.4f} | {(plain_se / r.std_error) ** 2:.1f} |")
    print(f"Call européen, Black-Scholes = {exact:.4f}, N = {n:_}".replace("_", " "))
    print("| Méthode | Prix MC | Erreur type | Écart à BS | Gain de variance |")
    print("|---|---|---|---|---|")
    print("\n".join(rows))

    print("\nGrecques (call) :")
    g_bs, g_mc = bs_greeks(**P), mc_greeks(**P, n_paths=400_000, seed=42)
    print("| Grecque | Analytique | Monte Carlo |")
    print("|---|---|---|")
    for k in ("delta", "gamma", "vega"):
        print(f"| {k} | {g_bs[k]:.4f} | {g_mc[k]:.4f} |")

    print("\nAsiatique arithmétique (12 fixings, N = 100 000) :")
    geo = geometric_asian_price(**P, n_steps=12)
    a = mc_asian(**P, n_steps=12, n_paths=n, seed=42)
    b = mc_asian(**P, n_steps=12, n_paths=n, seed=42, control_variate=True)
    print(f"géométrique fermé = {geo:.4f}")
    print(f"simple   : {a.price:.4f} ± {a.std_error:.4f}")
    print(f"contrôle : {b.price:.4f} ± {b.std_error:.4f}  "
          f"(variance / {(a.std_error / b.std_error) ** 2:.0f})")


if __name__ == "__main__":
    convergence_figure()
    variance_reduction_figure()
    results_table()
