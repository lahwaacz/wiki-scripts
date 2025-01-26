#! /usr/bin/env python3

import pytest
import sqlalchemy
from pytest_postgresql import factories

pg_executable = "/usr/bin/pg_ctl"
db_name = "wiki_scripts"

# postgresql process fixture
postgresql_proc = factories.postgresql_proc(logs_prefix="pytest-", executable=pg_executable)
# fixture holding an instance of a psycopg connection
postgresql = factories.postgresql("postgresql_proc", dbname=db_name)

@pytest.fixture(scope="function")
def pg_engine(postgresql):
    return sqlalchemy.create_engine("postgresql+psycopg://", poolclass=sqlalchemy.pool.StaticPool, creator=lambda: postgresql)

__all__ = ("postgresql_proc", "postgresql", "pg_engine")
