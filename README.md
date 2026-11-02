# PowerSite

A command-line tool that ranks candidate US data center sites by simulated investment return. It combines real public data (power prices, grid interconnection queues, climate) with a Monte Carlo IRR model for a wholesale-colocation-style build.

> **Read this first:** the model is a work in progress. Several inputs are placeholders (see [Known limitations](#known-limitations)), and the headline IRRs are very sensitive to capex. At the published average capex of about $17.6M/MW, the median IRR is roughly 8%, not the 18% you get at the model's $9M/MW default. Treat outputs as a framework for comparing sites, not as investment advice.

## Install

```bash
git clone https://github.com/ekche/powersite.git
cd powersite
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install openpyxl
```

## Get the data

```bash
powersite fetch-data
```

This downloads and builds, under `data/` (git-ignored):

- **EIA** industrial electricity prices by state
- **Grid congestion index** from the LBNL *Queued Up* dataset (state-level queue years where available, regional otherwise)
- **Climate / PUE estimate** from 2025 hourly temperature (free-cooling and hot-hour shares)

One step is manual: download the LBNL interconnection queue workbook (Berkeley Lab, *Queued Up*) and save it as:

## Commands

| Command | What it does |
|---|---|
| `powersite fetch-data` | Download and build all input data |
| `powersite rank --top 10` | Rank sites by simulated median IRR and P(IRR < 8%) |
| `powersite simulate --site "Dallas County, TX" --mw 100` | Monte Carlo IRR distribution for one site |
| `powersite sensitivity --site "Dallas County, TX"` | Tornado-style table: IRR swing from +/-20% on each input |
| `powersite breakeven --site "Dallas County, TX"` | Capex and rent needed to hit an 8% IRR |
| `powersite scenarios --site "Dallas County, TX"` | IRR across rent-escalator and capex-timing assumptions |

## Inputs and sources

| Input | Source | Status |
|---|---|---|
| Power price | EIA state industrial prices | Real data |
| Grid wait | LBNL Queued Up, scaled to a 30-month baseline | Real index, placeholder baseline |
| PUE | Estimated from 2025 hourly temperature | Estimate |
| Rent ($/kW-month) | `config/rents.csv` (CBRE and trade sources) | Sourced |
| Water risk | Hand-assigned 0-1 score | Placeholder |
| Capex | $9.0M/MW default (published range $8.9M-$23.3M, avg $17.6M, Cushman & Wakefield 2026) | Default is at the low end |
| Rent escalator | 2.5%/yr | Placeholder |
| Share of capex spent before power | 15% | Placeholder |

## Known limitations

- **Capex dominates.** Dallas median IRR at $9M / $13M / $17.6M per MW is 18.4% / 12.4% / 8.3%. Dallas and Loudoun are nearly identical at every capex level.
- **Escalator and capex timing are placeholders.** Adding them lifted Dallas from 12.8% to 18.4% and collapsed the grid-delay penalty. `powersite scenarios` shows the range (13.6% to 19.7%).
- **Site list is small** (8 counties) and water risk is a hand-set score.
- **Modeled terminal value** is 30% of capex at year 15.
- See `CHANGELOG.md` for how each change moved the results.
