import pytest

from app.config import Paths


@pytest.fixture
def paths(tmp_path) -> Paths:
    p = Paths(tmp_path)
    p.ensure()
    return p
