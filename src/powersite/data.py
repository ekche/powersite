import os
from pathlib import Path

import pandas as pd
import requests

RAW_DIR = Path("data/raw")
EIA_URL = "https://api.eia.gov/v2/electricity/retail-sales/data/"


def fetch_eia_prices(start: str = "2022") -> pd.DataFrame:
    """Industrial electricity prices by state from the EIA API, in $/MWh."""
    key = os.environ.get("EIA_API_KEY")
    if not key:
        raise RuntimeError("EIA_API_KEY is not set. Get one at eia.gov/opendata")
    params = {
        "api_key": key,
        "frequency": "annual",
        "data[0]": "price",
        "facets[sectorid][]": "IND",
        "start": start,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": 5000,
    }
    resp = requests.get(EIA_URL, params=params, timeout=60)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json()["response"]["data"])
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["usd_per_mwh"] = (df["price"] * 10).round(2)  # cents/kWh -> $/MWh
    df = df[(df["stateid"].str.len() == 2) & (df["stateid"] != "US")]
    out = df[["period", "stateid", "stateDescription", "usd_per_mwh"]].dropna()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out.to_csv(RAW_DIR / "eia_industrial_prices.csv", index=False)
    return out


STATE_REGION = {"VA": "PJM", "AZ": "West", "TX": "ERCOT", "GA": "Southeast",
                "OR": "West", "WY": "West", "IA": "MISO", "NV": "West"}


def build_grid_wait(min_n: int = 15) -> pd.DataFrame:
    """Median years from interconnection request to operation (COD >= 2020), by state."""
    src = RAW_DIR / "lbnl_queued_up.xlsx"
    q = pd.read_excel(src, sheet_name="03. Complete Queue Data", header=1)
    for c in ["q_date", "on_date"]:
        q[c] = pd.to_datetime(q[c], errors="coerce")
    op = q[(q["q_status"] == "operational") & q["on_date"].notna() & q["q_date"].notna()].copy()
    op["yrs"] = (op["on_date"] - op["q_date"]).dt.days / 365.25
    op = op[(op["on_date"].dt.year >= 2020) & (op["yrs"] > 0)]
    national = op["yrs"].median()
    by_region = op.groupby("region")["yrs"].median()
    by_state = op.groupby("state")["yrs"].agg(["count", "median"])
    rows = []
    for st, reg in STATE_REGION.items():
        if st in by_state.index and by_state.loc[st, "count"] >= min_n:
            yrs, basis = by_state.loc[st, "median"], "state"
        elif reg in by_region.index:
            yrs, basis = by_region[reg], f"region ({reg})"
        else:
            yrs, basis = national, "national"
        rows.append({"state": st, "queue_years": round(float(yrs), 2),
                     "congestion_index": round(float(yrs / national), 3), "basis": basis})
    out = pd.DataFrame(rows)
    out.to_csv(RAW_DIR / "grid_wait.csv", index=False)
    return out
