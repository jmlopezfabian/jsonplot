"""Pages that are built, not written.

Everything here has a source of truth in the code: the gallery is the contracts
in `examples/gallery.py` actually rendered, the CLI page is argparse's own help,
the error page is the `Code` class, and the notebook is the committed one. A
page transcribed by hand from any of those is a page that goes stale — the same
argument the framework makes about the contract itself.

Run by mkdocs-gen-files during the build; the files never touch the repo.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

import mkdocs_gen_files

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))

import matplotlib                                    # noqa: E402
matplotlib.use("Agg")

import jsonplot as jp                                # noqa: E402
from jsonplot.binding.errors import Code             # noqa: E402
from jsonplot.cli import main as cli_main            # noqa: E402

from gallery import CONTRACTS                        # noqa: E402
from sample_data import sales                        # noqa: E402


# --------------------------------------------------------------------------
# The gallery: every contract, drawn, next to the contract that drew it
# --------------------------------------------------------------------------

INTRO = """# Gallery

Every chart below was produced during this build by `jp.plot(contract, df)` on
the same 2,000-row DataFrame (`examples/sample_data.py`). The contract under
each one is the *whole* input — there is no other code.

Copy one, change the column names, and it will draw your data.
"""

TITLES = {
    "01_bars": "Bars",
    "02_grouped_bars": "Grouped bars",
    "03_stacked_bars": "Stacked bars",
    "04_top_n": "Top N, horizontal",
    "05_time_series": "Time series",
    "06_stacked_area": "Stacked area",
    "07_scatter": "Scatter, with size",
    "08_continuous_color": "Scatter, continuous color",
    "09_histogram": "Histogram",
    "10_box": "Box plot",
    "11_facets": "Facets",
    "12_seaborn": "Seaborn backend",
}


def gallery() -> None:
    df = sales()
    lines = [INTRO]
    for name, contract in CONTRACTS.items():
        figure = jp.plot(contract, df)
        buffer = io.BytesIO()
        figure.savefig(buffer, dpi=130, bbox_inches="tight", format="png")
        matplotlib.pyplot.close(figure)
        image = f"images/{name}.png"
        with mkdocs_gen_files.open(image, "wb") as fh:
            fh.write(buffer.getvalue())

        lines += [
            f"## {TITLES.get(name, name)}",
            "",
            f"![{name}]({image})",
            "",
            "```json",
            json.dumps(contract, indent=2),
            "```",
            "",
        ]
    write("gallery.md", "\n".join(lines))


# --------------------------------------------------------------------------
# The CLI page: argparse's own help, so a new flag documents itself
# --------------------------------------------------------------------------

COMMANDS = ["render", "validate", "describe", "contract", "schema", "types"]


def help_text(*argv: str) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
        cli_main([*argv, "--help"])
    return out.getvalue().rstrip()


def cli() -> None:
    lines = [
        "# From the terminal",
        "",
        "Installing the package puts `jsonplot` on the path. Everything the",
        "library does is reachable without writing Python: render a contract,",
        "validate one against a CSV, print the contract for a prompt.",
        "",
        "```bash",
        "jsonplot render contract.json data.csv -o chart.png",
        "jsonplot validate contract.json data.csv   # exits 1, writes the errors as JSON",
        "jsonplot describe data.csv                 # the column block for a prompt",
        "jsonplot contract data.csv                 # the whole contract, for a prompt",
        "jsonplot schema                            # the contract's JSON Schema",
        "jsonplot types                             # what this installation can draw",
        "```",
        "",
        "!!! tip \"Keeping a copy of the contract honest\"",
        "",
        "    `jsonplot contract -o docs/CONTRACT.md --check` exits 1 when the file",
        "    on disk no longer matches what the code would generate. It is what",
        "    keeps [The contract](CONTRACT.md) in this site true, and it belongs",
        "    in CI.",
        "",
        "## Every command",
        "",
        "*Generated from argparse during the build — a new flag appears here on",
        "its own.*",
        "",
        "```",
        help_text(),
        "```",
        "",
    ]
    for command in COMMANDS:
        lines += [f"### `jsonplot {command}`", "", "```", help_text(command), "```", ""]
    write("cli.md", "\n".join(lines))


# --------------------------------------------------------------------------
# The error page: the codes, from the class that defines them
# --------------------------------------------------------------------------

MEANING = {
    "INVALID_JSON": "The contract could not be parsed as JSON at all.",
    "UNKNOWN_FIELD": "A key the contract does not define. The spec is closed on "
                     "purpose: a silently ignored key is a chart that quietly "
                     "isn't what was asked for.",
    "MISSING_FIELD": "A required key is absent.",
    "INVALID_VALUE": "The key exists; the value is not one it accepts.",
    "UNSUPPORTED_VERSION": "The contract declares a `version` this build does not speak.",
    "COLUMN_NOT_FOUND": "A `field` names a column the DataFrame does not have. "
                        "The most common failure by a wide margin, and the "
                        "reason `did_you_mean` exists.",
    "TYPE_MISMATCH": "The column's type is not one the channel accepts — a date "
                     "on a channel that needs a number, say.",
    "AGGREGATE_REQUIRED": "The discrete axis repeats rows and the measure has no "
                          "`aggregate`, so there is no single value to draw.",
    "AGGREGATE_INVALID": "The aggregation cannot apply to that column: `mean` "
                         "over text, for instance.",
    "CARDINALITY_TOO_HIGH": "More categories than the palette can keep apart. "
                            "Fold the tail, filter, or facet — a ninth color is "
                            "not the answer.",
    "CHANNEL_NOT_SUPPORTED": "That chart type does not take that channel.",
    "MISSING_CHANNEL": "A channel the chart type requires was not given.",
    "EMPTY_RESULT": "The filters left nothing to draw.",
    "RENDERER_NOT_FOUND": "No renderer for this `viz_type` on this `backend` — "
                          "often an optional dependency that is not installed.",
}


def errors() -> None:
    codes = [c for c in vars(Code) if c.isupper()]
    lines = [
        "# Errors",
        "",
        "A contract is often written by a model that has never seen the data, so",
        "a validation failure is the normal case, not the exception. Errors are",
        "objects, not tracebacks:",
        "",
        "```python",
        "import jsonplot as jp",
        "",
        "for error in jp.validate(spec, df):",
        "    print(error.code, error.path, error.hint, error.did_you_mean)",
        "```",
        "",
        "```json",
        json.dumps([{
            "code": "COLUMN_NOT_FOUND",
            "path": "encoding.y.field",
            "message": "column 'revenu' is not in the DataFrame",
            "hint": "use one of the columns returned by describe_dataframe(df)",
            "did_you_mean": ["revenue"],
        }], indent=2),
        "```",
        "",
        "`validate` returns **every** error rather than the first: a model repairs",
        "better when it can see them all in one turn. `plot` raises",
        "`SpecErrorGroup`, which carries the same list and serializes with",
        "`.to_json()`.",
        "",
        "## The codes",
        "",
        "They are stable — part of the public API, safe to branch on.",
        "",
        "| Code | What it means |",
        "| --- | --- |",
    ]
    for code in codes:
        lines.append(f"| `{code}` | {MEANING.get(code, '')} |")
    lines += [
        "",
        "!!! note \"The repair loop\"",
        "",
        "    `jsonplot.agent.repair(spec, df, fix)` runs validate → fix → validate",
        "    for a bounded number of attempts, where `fix` is your call to a model.",
        "    See [Driving it from an agent](agents.md), or the notebook, where",
        "    Pydantic AI's `ModelRetry` runs the same loop.",
        "",
    ]
    write("errors.md", "\n".join(lines))


# --------------------------------------------------------------------------
# The notebook, copied in so mkdocs-jupyter can render it with its outputs
# --------------------------------------------------------------------------


def notebook() -> None:
    source = ROOT / "examples" / "pydantic_ai_agent.ipynb"
    with mkdocs_gen_files.open("notebook.ipynb", "wb") as fh:
        fh.write(source.read_bytes())
    mkdocs_gen_files.set_edit_path("notebook.ipynb", "examples/pydantic_ai_agent.ipynb")


def write(path: str, text: str) -> None:
    with mkdocs_gen_files.open(path, "w") as fh:
        fh.write(text)


gallery()
cli()
errors()
notebook()
