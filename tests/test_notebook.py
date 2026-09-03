"""The example notebook, checked without a model in the room.

Executing it needs Ollama and a few minutes, which is not a test. What is worth
asserting is that what got committed is a notebook that ran: valid nbformat,
cells that still compile against this version of the code, and no cell that
ended in a traceback.
"""

from pathlib import Path

import pytest

nbformat = pytest.importorskip("nbformat")

NOTEBOOK = Path(__file__).resolve().parents[1] / "examples" / "pydantic_ai_agent.ipynb"
#: `await` at the top level of a cell is legal in a kernel, not in a module.
ALLOW_TOP_LEVEL_AWAIT = 0x2000


@pytest.fixture(scope="module")
def nb():
    return nbformat.read(NOTEBOOK, as_version=4)


def test_it_is_a_valid_notebook(nb):
    nbformat.validate(nb)


def test_every_code_cell_compiles(nb):
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        source = "\n".join(line for line in cell.source.splitlines()
                           if not line.strip().startswith("%"))
        compile(source, f"cell {i}", "exec", flags=ALLOW_TOP_LEVEL_AWAIT, dont_inherit=True)


def test_it_was_committed_with_its_output_and_no_errors(nb):
    outputs = [out for cell in nb.cells if cell.cell_type == "code"
               for out in cell.get("outputs", [])]
    assert outputs, "the notebook was committed unexecuted"
    errors = [out for out in outputs if out.output_type == "error"]
    assert not errors, [f"{e.ename}: {e.evalue}" for e in errors]
    assert any("image/png" in out.get("data", {}) for out in outputs), \
        "no figure survived: the point of the notebook is the charts"
