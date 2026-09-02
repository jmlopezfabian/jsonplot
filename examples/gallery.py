"""Render one contract of each kind. `python examples/gallery.py out/`"""

from __future__ import annotations

import sys
from pathlib import Path

import jsonplot as jp
from sample_data import sales

CONTRACTS = {
    "01_bars": {
        "viz_type": "bar", "x_axis": "region", "y_axis": "revenue", "agg": "sum",
        "title": "Revenue by region", "annotate": True,
    },
    "02_grouped_bars": {
        "viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
        "group_by": "channel", "agg": "sum",
        "title": "Revenue by region and channel",
        "subtitle": "January 2024 – June 2025",
    },
    "03_stacked_bars": {
        "viz_type": "bar", "x_axis": "region", "y_axis": "units",
        "group_by": "channel", "agg": "sum", "stacked": True,
        "title": "Units sold",
    },
    "04_top_n": {
        "viz_type": "bar", "x_axis": "region", "y_axis": "revenue", "agg": "sum",
        "orientation": "horizontal", "sort": "-y", "limit": 3,
        "title": "The three best-selling regions", "annotate": True,
    },
    "05_time_series": {
        "viz_type": "line",
        "encoding": {
            "x": {"field": "date", "time_unit": "month"},
            "y": {"field": "revenue", "aggregate": "sum"},
            "color": {"field": "region"},
        },
        "title": "Monthly revenue by region",
    },
    "06_stacked_area": {
        "viz_type": "area", "x_axis": "date", "y_axis": "revenue", "agg": "sum",
        "time_unit": "quarter", "group_by": "channel", "stacked": True,
        "title": "Quarterly revenue by channel",
    },
    "07_scatter": {
        "viz_type": "scatter", "x_axis": "price", "y_axis": "revenue",
        "group_by": "channel", "size_by": "units",
        "title": "Unit price against order value",
    },
    "08_continuous_color": {
        "viz_type": "scatter", "x_axis": "price", "y_axis": "revenue",
        "encoding": {"color": {"field": "satisfaction"}},
        "title": "Satisfaction per order",
    },
    "09_histogram": {
        "viz_type": "hist", "x_axis": "satisfaction", "bins": 20,
        "title": "Distribution of satisfaction",
    },
    "10_box": {
        "viz_type": "box", "x_axis": "region", "y_axis": "price",
        "title": "Unit price by region",
    },
    "11_facets": {
        "viz_type": "line",
        "encoding": {
            "x": {"field": "date", "time_unit": "month"},
            "y": {"field": "revenue", "aggregate": "sum"},
            "color": {"field": "channel"},
            "facet": {"field": "region", "columns": 2},
        },
        "title": "Revenue by region and channel",
    },
    "12_seaborn": {
        "viz_type": "violin", "backend": "seaborn",
        "x_axis": "region", "y_axis": "satisfaction",
        "title": "Satisfaction by region",
    },
}


def main(destination: str = "out") -> None:
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    df = sales()
    for name, contract in CONTRACTS.items():
        fig = jp.plot(contract, df)
        fig.savefig(out / f"{name}.png", dpi=140, bbox_inches="tight")
        print(f"{name}.png")


if __name__ == "__main__":
    main(*sys.argv[1:])
