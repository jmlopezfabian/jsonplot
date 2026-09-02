"""A small reproducible dataset for the examples and the tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

REGIONS = ["North", "South", "Central", "East"]
CHANNELS = ["Store", "Online"]


def sales(n: int = 2000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", "2025-06-30", freq="D")
    df = pd.DataFrame({
        "date": rng.choice(dates, n),
        "region": rng.choice(REGIONS, n, p=[0.35, 0.25, 0.2, 0.2]),
        "channel": rng.choice(CHANNELS, n, p=[0.6, 0.4]),
        "units": rng.integers(1, 40, n),
        "price": np.round(rng.gamma(4, 12, n), 2),
        "satisfaction": np.clip(rng.normal(4.1, 0.7, n), 1, 5).round(1),
    })
    df["revenue"] = (df["units"] * df["price"]).round(2)
    return df.sort_values("date").reset_index(drop=True)
