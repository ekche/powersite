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
