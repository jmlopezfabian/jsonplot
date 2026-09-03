"""The site's navigation, checked without building the site.

Building the docs needs the `docs` group; this only needs the repo. What it
catches is the cheap half: a page renamed or removed while `mkdocs.yml` still
points at it, and a generated page whose script no longer produces it.
"""

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "mkdocs.yml"
DOCS = ROOT / "docs"

#: Pages that do not exist on disk because `scripts/gen_docs.py` writes them
#: during the build.
GENERATED = {"gallery.md", "cli.md", "errors.md", "notebook.ipynb"}


def nav_targets(nav) -> list[str]:
    """Every file path in the nav tree, however deeply nested."""
    if isinstance(nav, str):
        return [nav]
    if isinstance(nav, list):
        return [t for item in nav for t in nav_targets(item)]
    if isinstance(nav, dict):
        return [t for value in nav.values() for t in nav_targets(value)]
    return []


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8"))


def test_every_page_in_the_nav_exists(config):
    for target in nav_targets(config["nav"]):
        if target in GENERATED:
            continue
        assert (DOCS / target).exists(), f"{target} is in the nav but not in docs/"


def test_the_generated_pages_are_still_generated(config):
    source = (ROOT / "scripts" / "gen_docs.py").read_text(encoding="utf-8")
    in_nav = set(nav_targets(config["nav"]))
    for page in GENERATED:
        assert page in in_nav, f"{page} is generated but nothing links to it"
        assert page in source, f"nothing in gen_docs.py writes {page}"


def test_the_notebook_the_site_publishes_is_the_committed_one():
    assert (ROOT / "examples" / "pydantic_ai_agent.ipynb").exists()


def test_the_contract_page_is_the_generated_snapshot():
    """The site serves docs/CONTRACT.md, which `--check` keeps current."""
    assert (DOCS / "CONTRACT.md").read_text(encoding="utf-8").startswith(
        "# The visualization contract")
