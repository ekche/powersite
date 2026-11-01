import numpy as np
import numpy_financial as npf
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="PowerSite: where should a data center go, and what will it return?")
console = Console()

# PLACEHOLDER data. We replace this with real EIA / Berkeley Lab / NOAA data later.
SITES = [
    # name, $/MWh power, interconnect wait (months), water risk (0-1), PUE
    ("Loudoun County, VA", 72, 48, 0.35, 1.35),
    ("Maricopa County, AZ", 68, 36, 0.85, 1.45),
    ("Dallas County, TX", 58, 30, 0.50, 1.40),
    ("Douglas County, GA", 62, 28, 0.30, 1.38),
    ("Columbia County, OR", 45, 24, 0.25, 1.20),
    ("Cheyenne, WY", 50, 20, 0.40, 1.15),
    ("Polk County, IA", 52, 22, 0.20, 1.22),
    ("Storey County, NV", 66, 26, 0.80, 1.30),
]


from pathlib import Path

SITE_STATES = {
    "Loudoun County, VA": "VA", "Maricopa County, AZ": "AZ",
    "Dallas County, TX": "TX", "Douglas County, GA": "GA",
    "Columbia County, OR": "OR", "Cheyenne, WY": "WY",
    "Polk County, IA": "IA", "Storey County, NV": "NV",
}


def apply_real_prices():
    """Replace placeholder power prices with real EIA state prices if downloaded."""
    f = Path("data/raw/eia_industrial_prices.csv")
    if not f.exists():
        return
    import pandas as pd
    df = pd.read_csv(f)
    df = df[df["period"] == df["period"].max()]
    prices = dict(zip(df["stateid"], df["usd_per_mwh"]))
    for i, site in enumerate(SITES):
        st = SITE_STATES.get(site[0])
        if st in prices:
            SITES[i] = (site[0], float(prices[st]), *site[2:])


apply_real_prices()


def apply_real_wait(baseline_months=30):
    f = Path("data/raw/grid_wait.csv")
    if not f.exists():
        return
    import pandas as pd
    gw = pd.read_csv(f)
    idx = dict(zip(gw["state"], gw["congestion_index"]))
    for i, site in enumerate(SITES):
        st = SITE_STATES.get(site[0])
        if st in idx:
            SITES[i] = (site[0], site[1], round(baseline_months * float(idx[st]), 1), *site[3:])


apply_real_wait()


def apply_real_climate():
    f = Path("data/raw/climate.csv")
    if not f.exists():
        return
    import pandas as pd
    pue = dict(zip(*[pd.read_csv(f)[c] for c in ["site", "pue_est"]]))
    for i, site in enumerate(SITES):
        if site[0] in pue:
            SITES[i] = (*site[:4], float(pue[site[0]]))


apply_real_climate()


def score(price, wait, water, pue):
    return round(100 - 0.6 * price - 0.4 * wait - 25 * water - 30 * (pue - 1), 1)


@app.command()
def fetch_data():
    """Download and cache public datasets (EIA prices for now)."""
    from powersite.data import fetch_eia_prices
    with console.status("Fetching EIA industrial electricity prices..."):
        df = fetch_eia_prices()
    latest = df[df["period"] == df["period"].max()].sort_values("usd_per_mwh")
    table = Table(title=f"Industrial power price by state ({latest['period'].iloc[0]})")
    table.add_column("State"); table.add_column("$/MWh")
    for _, r in latest.head(10).iterrows():
        table.add_row(r["stateDescription"], f"{r['usd_per_mwh']:.1f}")
    console.print(table)
    console.print(f"[green]Saved {len(df)} rows to data/raw/eia_industrial_prices.csv[/green]")
    from powersite.data import build_grid_wait
    gw = build_grid_wait()
    t2 = Table(title="Grid congestion from LBNL Queued Up (years, request to operation)")
    for c in ["State", "Queue yrs", "Index", "Basis"]:
        t2.add_column(c)
    for _, r in gw.iterrows():
        t2.add_row(r["state"], str(r["queue_years"]), str(r["congestion_index"]), r["basis"])
    console.print(t2)
    from powersite.data import build_climate
    with console.status("Fetching climate data..."):
        cl = build_climate()
    t3 = Table(title="Climate and estimated PUE (2025 hourly temperature)")
    for c in ["Site", "Free-cooling share", "Hot-hours share", "PUE est."]:
        t3.add_column(c)
    for _, r in cl.iterrows():
        t3.add_row(r["site"], str(r["free_cooling_share"]), str(r["hot_hours_share"]), str(r["pue_est"]))
    console.print(t3)


@app.command()
def train():
    """Train forecasting and PUE models (coming soon)."""
    console.print("[yellow]TODO:[/yellow] power price forecast + PUE model")


@app.command()
def rank(
    top: int = typer.Option(10, help="How many sites to show"),
    runs: int = typer.Option(2000, help="Monte Carlo runs per site"),
):
    """Rank sites by simulated median IRR (100 MW)."""
    from powersite.model import simulate_irrs, get_rent
    results = []
    with console.status("Simulating each site..."):
        for site in SITES:
            irrs, failed = simulate_irrs(site, 100, runs)
            risk = ((irrs < 0.08).sum() + failed) / runs
            results.append((site, float(np.median(irrs)), float(risk)))
    results.sort(key=lambda r: r[1], reverse=True)
    table = Table(title=f"Top {min(top, len(results))} sites by simulated median IRR")
    for col in ["#", "Site", "Power $/MWh", "Grid wait (mo)", "Water risk", "PUE", "Rent $/kW-mo", "Median IRR", "P(IRR<8%)"]:
        table.add_column(col)
    for i, (s_, med, risk) in enumerate(results[:top], 1):
        table.add_row(str(i), s_[0], str(s_[1]), str(s_[2]), str(s_[3]), str(s_[4]),
                      f"{get_rent(s_[0]):.0f}", f"{med:.1%}", f"{risk:.1%}")
    console.print(table)


@app.command()
def simulate(
    site: str = typer.Option("Loudoun County, VA", help="Site name"),
    mw: int = typer.Option(100, help="Capacity in MW"),
    runs: int = typer.Option(10000, help="Monte Carlo runs"),
):
    """Monte Carlo IRR simulation for a site."""
    from powersite.model import simulate_irrs
    match = next((s_ for s_ in SITES if s_[0].lower() == site.lower()), None)
    if not match:
        console.print(f"[red]Unknown site.[/red] Try: {', '.join(s_[0] for s_ in SITES)}")
        raise typer.Exit(1)
    irrs, failed = simulate_irrs(match, mw, runs)
    table = Table(title=f"{match[0]}: {mw} MW, {runs:,} simulations")
    table.add_column("Metric"); table.add_column("Value")
    table.add_row("Median IRR", f"{np.median(irrs):.1%}")
    table.add_row("5th percentile (bad case)", f"{np.percentile(irrs, 5):.1%}")
    table.add_row("95th percentile (good case)", f"{np.percentile(irrs, 95):.1%}")
    table.add_row("Chance IRR < 8% (incl. failed runs)", f"{((irrs < 0.08).sum() + failed) / runs:.1%}")
    table.add_row("Runs with no valid IRR", f"{failed / runs:.1%}")
    console.print(table)


@app.command()
def sensitivity(
    site: str = typer.Option("Dallas County, TX", help="Site name"),
    swing: float = typer.Option(0.20, help="+/- change applied to each input"),
    runs: int = typer.Option(3000, help="Monte Carlo runs per case"),
):
    """Which inputs move IRR the most? (one at a time, +/- swing)"""
    from powersite.model import simulate_irrs
    base_site = next((s_ for s_ in SITES if s_[0].lower() == site.lower()), None)
    if not base_site:
        console.print(f"[red]Unknown site.[/red] Try: {', '.join(s_[0] for s_ in SITES)}")
        raise typer.Exit(1)
    name, price, wait, water, pue = base_site

    def med(st, **kw):
        irrs, _ = simulate_irrs(st, 100, runs, **kw)
        return float(np.median(irrs))

    cases = {
        "Rent": lambda f: med(base_site, rent_mult=f),
        "Capex": lambda f: med(base_site, capex_mult=f),
        "Power price": lambda f: med((name, price * f, wait, water, pue)),
        "Grid wait": lambda f: med((name, price, wait * f, water, pue)),
        "PUE": lambda f: med((name, price, wait, water, pue * f)),
        "Water risk": lambda f: med((name, price, wait, water * f, pue)),
    }
    base = med(base_site)
    rows = []
    with console.status("Running sensitivity cases..."):
        for k, fn in cases.items():
            lo, hi = fn(1 - swing), fn(1 + swing)
            rows.append((k, lo, hi, abs(hi - lo)))
    rows.sort(key=lambda r: r[3], reverse=True)
    table = Table(title=f"{base_site[0]}: base median IRR {base:.1%}, each input +/-{swing:.0%}")
    for col in ["Input", f"IRR at -{swing:.0%}", f"IRR at +{swing:.0%}", "Swing (pts)"]:
        table.add_column(col)
    for k, lo, hi, sw in rows:
        table.add_row(k, f"{lo:.1%}", f"{hi:.1%}", f"{sw * 100:.1f}")
    console.print(table)


@app.command()
def breakeven(
    site: str = typer.Option("Dallas County, TX", help="Site name"),
    hurdle: float = typer.Option(0.08, help="Target median IRR"),
    runs: int = typer.Option(2000, help="Monte Carlo runs per step"),
):
    """What capex ($M/MW) or rent ($/kW-mo) makes the site just hit the hurdle IRR?"""
    from powersite.model import simulate_irrs, get_rent
    st = next((s_ for s_ in SITES if s_[0].lower() == site.lower()), None)
    if not st:
        console.print(f"[red]Unknown site.[/red] Try: {', '.join(s_[0] for s_ in SITES)}")
        raise typer.Exit(1)
    BASE_CAPEX = 9.0  # $M/MW, the model's current placeholder

    def med(**kw):
        irrs, _ = simulate_irrs(st, 100, runs, **kw)
        return float(np.median(irrs)) if len(irrs) else -1.0

    def solve(f, lo, hi, increasing):
        for _ in range(14):
            mid = (lo + hi) / 2
            if (f(mid) > hurdle) == increasing:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    with console.status("Solving..."):
        base_irr = med()
        capex_m = solve(lambda m: med(capex_mult=m), 0.5, 3.0, False)
        rent_m = solve(lambda m: med(rent_mult=m), 0.5, 3.0, True)
    rent = get_rent(st[0])
    table = Table(title=f"{st[0]}: what does it take to earn {hurdle:.0%}?")
    table.add_column("Metric"); table.add_column("Value")
    table.add_row("Median IRR at model defaults", f"{base_irr:.1%}")
    table.add_row("Model capex / rent", f"${BASE_CAPEX:.1f}M per MW / ${rent:.0f} per kW-mo")
    table.add_row("Break-even capex at current rent", f"${BASE_CAPEX * capex_m:.1f}M per MW")
    table.add_row("Break-even rent at ${:.1f}M capex".format(BASE_CAPEX), f"${rent * rent_m:.0f} per kW-mo")
    table.add_row("Published US/Canada capex (C&W 2026)", "$8.9M to $23.3M per MW, avg $17.6M")
    console.print(table)


if __name__ == "__main__":
    app()
