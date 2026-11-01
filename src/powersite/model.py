import numpy as np
import numpy_financial as npf
from pathlib import Path

DEFAULT_RENT = 158.0  # $/kW-month, the old single placeholder


def get_rent(site_name):
    f = Path("config/rents.csv")
    if f.exists():
        import pandas as pd
        df = pd.read_csv(f)
        row = df[df["site"] == site_name]
        if len(row):
            return float(row["rent_kw_month"].iloc[0])
    return DEFAULT_RENT

PUE_CAP = 1.30            # PLACEHOLDER: tenant pays power only up to this PUE
WATER_COST_PER_MW = 100_000  # PLACEHOLDER: $/MW-year at water risk = 1.0


def simulate_irrs(site, mw=100, runs=10000, seed=42):
    """Monte Carlo IRRs for one site tuple (name, $/MWh, grid wait months, water risk, PUE).
    Returns (valid IRR array, number of runs with no valid IRR)."""
    _, price, wait, water, pue = site
    rng = np.random.default_rng(seed)
    rent = get_rent(site[0])
    irrs, failed = [], 0
    for _ in range(runs):
        capex = rng.normal(9.0e6, 1.2e6) * mw
        revenue = rng.normal(rent * 12_000, rent * 12_000 * 0.13) * mw
        p = rng.normal(price, price * 0.2)
        it_cost = 8760 * 0.7 * p * mw                    # energy cost of IT load
        total_power = it_cost * pue
        recovered = it_cost * min(pue, PUE_CAP) * rng.uniform(0.85, 1.0)
        net = revenue - total_power + recovered - 150_000 * mw - WATER_COST_PER_MW * water * mw
        delay = int(rng.poisson(wait / 12))
        flows = [-capex] + [0] * delay + [net] * 15
        flows[-1] += 0.3 * capex
        irr = npf.irr(flows)
        if np.isnan(irr):
            failed += 1
        else:
            irrs.append(irr)
    return np.array(irrs), failed
