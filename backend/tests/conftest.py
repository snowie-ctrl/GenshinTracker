import pytest

from app.config import Paths


@pytest.fixture
def paths(tmp_path) -> Paths:
    p = Paths(tmp_path)
    p.ensure()
    return p


from app.db.engine import make_engine, make_session_factory, migrate  # noqa: E402


@pytest.fixture
def session_factory(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    yield make_session_factory(engine)
    engine.dispose()
