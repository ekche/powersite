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


@app.command()
def train():
    """Train forecasting and PUE models (coming soon)."""
    console.print("[yellow]TODO:[/yellow] power price forecast + PUE model")


@app.command()
def rank(top: int = typer.Option(10, help="How many sites to show")):
    """Rank candidate sites by overall score."""
    rows = sorted(SITES, key=lambda s: score(*s[1:]), reverse=True)[:top]
    table = Table(title=f"Top {len(rows)} data center sites")
    for col in ["#", "Site", "Power $/MWh", "Grid wait (mo)", "Water risk", "PUE", "Score"]:
        table.add_column(col)
    for i, s in enumerate(rows, 1):
        table.add_row(str(i), s[0], str(s[1]), str(s[2]), str(s[3]), str(s[4]), str(score(*s[1:])))
    console.print(table)


@app.command()
def simulate(
    site: str = typer.Option("Loudoun County, VA", help="Site name"),
    mw: int = typer.Option(100, help="Capacity in MW"),
    runs: int = typer.Option(10000, help="Monte Carlo runs"),
):
    """Monte Carlo IRR simulation for a site."""
    match = next((s for s in SITES if s[0].lower() == site.lower()), None)
    if not match:
        console.print(f"[red]Unknown site.[/red] Try: {', '.join(s[0] for s in SITES)}")
        raise typer.Exit(1)
    _, price, wait, _, pue = match
    rng = np.random.default_rng(42)
    irrs = []
    for _ in range(runs):
        capex = rng.normal(9.0e6, 1.2e6) * mw              # $ per MW
        revenue = rng.normal(1.2e6, 0.2e6) * mw            # $ per MW-year
        p = rng.normal(price, price * 0.2)                 # power price shock
        power_cost = 8760 * 0.7 * pue * p * mw
        recovered = power_cost * rng.uniform(0.85, 1.0)  # tenant pays 85-100% of power
        net = revenue - power_cost + recovered - 150_000 * mw
        delay = int(rng.poisson(wait / 12))                # interconnect delay (years)
        flows = [-capex] + [0] * delay + [net] * 15
        irr = npf.irr(flows)
        if not np.isnan(irr):
            irrs.append(irr)
    irrs = np.array(irrs)
    table = Table(title=f"{site}: {mw} MW, {len(irrs):,} simulations")
    table.add_column("Metric"); table.add_column("Value")
    table.add_row("Median IRR", f"{np.median(irrs):.1%}")
    table.add_row("5th percentile (bad case)", f"{np.percentile(irrs, 5):.1%}")
    table.add_row("95th percentile (good case)", f"{np.percentile(irrs, 95):.1%}")
    table.add_row("Chance IRR < 8%", f"{(irrs < 0.08).mean():.1%}")
    console.print(table)


if __name__ == "__main__":
    app()
