"""Test de fumée : chaque page du dashboard se charge sans exception sur la base réelle."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_DIR = Path(__file__).resolve().parents[1] / "app"
PAGES = [APP_DIR / "streamlit_app.py", *sorted((APP_DIR / "pages").glob("*.py"))]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.stem)
def test_page_loads(page: Path) -> None:
    at = AppTest.from_file(str(page), default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
