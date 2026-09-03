"""A contract editor, live.

    uv run streamlit run examples/streamlit_app.py

Write a contract on the left, see the chart on the right — or the errors, which
is the point: this is what an agent's repair loop looks like with a human
holding the loop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

import jsonplot as jp
import jsonplot.streamlit as jps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sample_data import sales  # noqa: E402

PRESETS: dict[str, dict] = {
    "Revenue by region": {
        "viz_type": "bar", "x_axis": "region", "y_axis": "revenue",
        "agg": "sum", "sort": "-y", "title": "Revenue by region",
    },
    "Monthly revenue by channel": {
        "viz_type": "line", "x_axis": "date", "y_axis": "revenue",
        "group_by": "channel", "agg": "sum", "time_unit": "month",
        "title": "Monthly revenue", "subtitle": "By channel",
    },
    "Price vs revenue": {
        "viz_type": "scatter", "x_axis": "price", "y_axis": "revenue",
        "group_by": "region", "title": "Price vs revenue",
    },
    "Satisfaction spread": {
        "viz_type": "box", "x_axis": "region", "y_axis": "satisfaction",
        "backend": "seaborn", "title": "Satisfaction by region",
    },
    "Faceted units": {
        "viz_type": "hist", "x_axis": "units", "facet_by": "region",
        "bins": 20, "title": "Units per order",
    },
    "A contract that fails": {
        "viz_type": "bar", "x_axis": "regionn", "y_axis": "revenue",
        "agg": "total",
    },
}


@st.cache_data
def data():
    return sales()


@st.cache_data(show_spinner=False)
def rendered(contract: str, theme: str) -> bytes:
    """Memoized on the contract text and the theme: editing re-renders, a
    click anywhere else does not."""
    return jps.png(contract, data(), theme=theme)


st.set_page_config(page_title="jsonplot · contract editor", layout="wide")
st.title("jsonplot")
st.caption("A JSON contract and a DataFrame go in; a figure comes out.")

df = data()
editor, canvas = st.columns([2, 3], gap="large")

with editor:
    preset = st.selectbox("Preset", list(PRESETS))
    contract = st.text_area(
        "Contract", json.dumps(PRESETS[preset], indent=2), height=340,
        key=f"contract-{preset}",
    )
    choice = st.radio("Theme", ["auto", "clean", "dark"], horizontal=True)
    theme = jps.active_theme() if choice == "auto" else choice

    with st.expander("The data"):
        st.dataframe(df.head(20))
        st.json(jp.describe_dataframe(df), expanded=False)

with canvas:
    errors = jps.st_plot(contract, df, theme=theme)
    if errors:
        st.info("Fix the contract on the left. Each error above is a JSON object "
                "an agent can read: code, path, hint, did_you_mean.")
    else:
        st.download_button("Download PNG", rendered(contract, theme),
                           file_name="chart.png", mime="image/png")
        with st.expander("What the contract resolved to"):
            st.json(jp.inspect(json.loads(contract), df))
