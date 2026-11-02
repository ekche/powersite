# PowerSite

A command-line tool that ranks candidate US data center sites by simulated investment return. It combines real public data (power prices, grid interconnection queues, climate) with a Monte Carlo IRR model for a wholesale-colocation-style build.

> **Read this first:** the model is a work in progress. Several inputs are placeholders (see Known limitations), and the headline IRRs are very sensitive to capex. At the published average capex of about $17.6M/MW, only Dallas and Loudoun (the two $165/kW-month rent sites) come out near 8% (8.3% and 8.4%); the other six sites fall to 3.2% to 4.2%, from 10.6% to 12.2% at the model's $9M/MW default. Treat outputs as a framework for comparing sites, not as investment advice.

## Install

```bash
git clone https://github.com/ekche/powersite.git
cd powersite
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Get the data

Run these steps from the repository root.

1. Download the LBNL interconnection queue workbook (Berkeley Lab, *Queued Up*) and save it as `data/raw/lbnl_queued_up.xlsx`.
2. Get a free EIA API key at https://www.eia.gov/opendata/ and set it (replace the placeholder with your real key):

```bash
export EIA_API_KEY=your_key_here
```

3. Build the datasets:

```bash
powersite fetch-data
```

This writes, under `data/` (git-ignored):

- **EIA** industrial electricity prices by state
- **Grid congestion index** from the LBNL *Queued Up* dataset (state-level queue years where available, regional otherwise)
- **Climate / PUE estimate** from 2025 hourly temperature (free-cooling and hot-hour shares)

Without `fetch-data`, `rank` and `simulate` still run, but with built-in placeholder power prices, grid waits and PUE values, so results will differ from the real-data numbers in this README.

## Commands

| Command | What it does |
|---|---|
| `powersite fetch-data` | Download EIA and climate data and build the grid-wait index (needs the LBNL file first) |
| `powersite rank --top 10` | Rank sites by simulated median IRR (also shows P(IRR < 8%)) |
| `powersite simulate --site "Dallas County, TX" --mw 100` | Monte Carlo IRR distribution for one site |
| `powersite sensitivity --site "Dallas County, TX"` | IRR swing from +/-20% on each input |
| `powersite breakeven --site "Dallas County, TX"` | Capex and rent needed to hit an 8% IRR |
| `powersite scenarios --site "Dallas County, TX"` | IRR across rent-escalator and capex-timing assumptions |

## Inputs and sources

| Input | Source | Status |
|---|---|---|
| Power price | EIA state industrial prices | Real data |
| Grid wait | LBNL Queued Up, scaled to a 30-month baseline | Real index, placeholder baseline |
| PUE | Estimated from 2025 hourly temperature (Open-Meteo historical archive) | Estimate |
| Rent ($/kW-month) | `config/rents.csv`: Datacentres.com Aug 2026 ranges (NoVA/DFW, Phoenix, Atlanta), midpoints | 4 of 8 sites sourced; Oregon, Wyoming, Iowa and Nevada are assumed at $115 |
| Water risk | Hand-assigned 0-1 score | Placeholder |
| Capex | $9.0M/MW default (published range $8.9M-$23.3M, avg $17.6M, Cushman & Wakefield 2026) | Default is far below the published average |
| Rent escalator | 2.5%/yr | Placeholder |
| Share of capex spent before power | 15% | Placeholder |

## Known limitations

- **Capex dominates.** Median IRR at $9M / $13M / $17.6M per MW: Dallas 18.4% / 12.4% / 8.3%, Loudoun 18.3% / 12.4% / 8.4%, and the other six sites 10.6-12.2% / 6.1-7.4% / 3.2-4.2%. At $13M/MW and above, only the two $165 rent sites clear an 8% IRR.
- **Escalator and capex timing are placeholders.** Adding them lifted Dallas from 12.8% to 18.4% and collapsed the grid-delay penalty. `powersite scenarios` shows the range for Dallas at the $9M default (13.6% to 19.7%).
- **Capex is the same for every site**, although published costs vary by market (coverage reports Texas among the cheaper markets), so the $17.6M case is pessimistic for Dallas.
- **Site list is small** (8 sites) and water risk is a hand-set score.
- **Modeled terminal value** is 30% of capex at year 15.
- **Unlevered, pre-tax IRR.** Assumes full lease-up from day one; tenants reimburse power up to PUE 1.30.
- **Grid wait is a proxy.** LBNL Queued Up measures generation interconnection, not data center load interconnection.
- **Power price barely moves IRR** (about 0.2 points per +/-20%) because tenants reimburse most power cost, and water risk has a similarly small modeled effect; site ranking is driven mainly by rent and capex, and small gaps between sites are within noise.
- **Run from the repo root.** Data and rent files are read relative to the current directory; otherwise defaults are used silently.
- **Four of eight rents are assumptions** (Columbia, Cheyenne, Polk, Storey at $115), so their IRRs and relative order reflect that assumption, not market data. Dallas and Loudoun share one rent figure, so their near-identical results are partly by construction.
- See `CHANGELOG.md` for how each change moved the results.

## Data attribution

- Electricity prices: U.S. Energy Information Administration (EIA) Open Data.
- Interconnection queues: Lawrence Berkeley National Laboratory, *Queued Up*.
- Historical weather: [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0); see their terms for usage limits.
- Rents: Datacentres.com market ranges (Aug 2026), as listed in `config/rents.csv`.
