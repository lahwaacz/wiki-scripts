#! /usr/bin/env python3

import pytest
from pytest_postgresql import factories
import sqlalchemy

pg_executable = "/usr/bin/pg_ctl"
db_name = "wiki_scripts"

# postgresql process fixture
postgresql_proc = factories.postgresql_proc(logs_prefix="pytest-", executable=pg_executable)
# fixture holding an instance of a psycopg2 connection
postgresql = factories.postgresql("postgresql_proc", db_name=db_name)

@pytest.fixture(scope="function")
def pg_engine(postgresql):
    return sqlalchemy.create_engine("postgresql+psycopg2://", poolclass=sqlalchemy.pool.StaticPool, creator=lambda: postgresql)

__all__ = ("postgresql_proc", "postgresql", "pg_engine")
