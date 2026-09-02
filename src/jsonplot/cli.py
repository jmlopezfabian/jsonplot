"""jsonplot from the terminal.

    jsonplot render contract.json data.csv -o chart.png
    jsonplot validate contract.json data.csv
    jsonplot describe data.csv
    jsonplot schema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from . import agent, api
from .binding.errors import SpecErrorGroup
from .spec.schema import json_schema


def _read_data(path: str, parse_dates: bool = True) -> pd.DataFrame:
    suffix = Path(path).suffix.lower()
    if suffix in (".parquet", ".pq"):
        df = pd.read_parquet(path)
    elif suffix in (".json", ".ndjson"):
        df = pd.read_json(path, lines=suffix == ".ndjson")
    else:
        df = pd.read_csv(path)
    return _infer_dates(df) if parse_dates else df


def _infer_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Convert text columns that are dates all the way through.

    A CSV carries no types, and without this any contract using `time_unit`
    would fail with a TYPE_MISMATCH that is not the author's fault.
    """
    for col in df.columns:
        if df[col].dtype != "object" and not isinstance(df[col].dtype, pd.StringDtype):
            continue
        sample = df[col].dropna().head(200)
        if sample.empty:
            continue
        try:
            converted = pd.to_datetime(sample, format="ISO8601")
        except (ValueError, TypeError):
            continue
        if converted.notna().all():
            df[col] = pd.to_datetime(df[col], format="ISO8601", errors="coerce")
    return df


def _read_spec(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jsonplot", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_render = sub.add_parser("render", help="draw the contract")
    p_render.add_argument("spec")
    p_render.add_argument("data")
    p_render.add_argument("-o", "--out", default="plot.png")
    p_render.add_argument("--dpi", type=int, default=150)
    p_render.add_argument("--no-parse-dates", action="store_true",
                          help="leave text columns as text")

    p_val = sub.add_parser("validate", help="validate without drawing")
    p_val.add_argument("spec")
    p_val.add_argument("data", nargs="?")

    p_desc = sub.add_parser("describe", help="dataset summary for the prompt")
    p_desc.add_argument("data")

    sub.add_parser("schema", help="print the contract's JSON Schema")
    sub.add_parser("types", help="available chart types and backends")

    args = parser.parse_args(argv)

    if args.cmd == "schema":
        print(json.dumps(json_schema(), indent=2, ensure_ascii=False))
        return 0
    if args.cmd == "types":
        for viz, backends in api.supported().items():
            print(f"{viz:10s} {', '.join(backends)}")
        return 0
    if args.cmd == "describe":
        print(agent.context(_read_data(args.data)))
        return 0

    spec = _read_spec(args.spec)

    if args.cmd == "validate":
        df = _read_data(args.data) if args.data else None
        errors = api.validate(spec, df)
        if not errors:
            print("contract is valid")
            return 0
        print(agent.errors_as_json(errors), file=sys.stderr)
        return 1

    try:
        fig = api.plot(spec, _read_data(args.data, not args.no_parse_dates))
    except SpecErrorGroup as exc:
        print(exc.to_json(indent=2), file=sys.stderr)
        return 1
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
