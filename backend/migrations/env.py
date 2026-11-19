from alembic import context
from sqlalchemy import create_engine

from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:  # plain `alembic` CLI use (e.g. `alembic revision --autogenerate`)
    with create_engine(config.get_main_option("sqlalchemy.url")).connect() as conn:
        _run(conn)
