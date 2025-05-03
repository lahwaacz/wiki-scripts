from typing import Iterator

import pytest
import pytest_docker
import sqlalchemy as sa

from ws.db.database import Database

__all__ = [
    "wiki_scripts_database_url",
    "db",
]


@pytest.fixture(scope="session")
def wiki_scripts_database_url(
    containers_dotenv_values: dict[str, str | None],
    docker_ip: str,
    docker_services: pytest_docker.Services,
) -> sa.URL:
    """Ensure that MediaWiki's database is up and responsive."""
    # port_for takes a container port and returns the corresponding host port
    port = docker_services.port_for("wiki-scripts-database", 5432)
    database = containers_dotenv_values.get("WIKI_SCRIPTS_DB")
    user = containers_dotenv_values.get("WIKI_SCRIPTS_USER")
    password = containers_dotenv_values.get("WIKI_SCRIPTS_PASSWORD")
    url = sa.URL.create(
        drivername="postgresql+psycopg",
        host=docker_ip,
        port=port,
        database=database,
        username=user,
        password=password,
    )
    engine = sa.create_engine(url)

    def try_connect():
        try:
            with engine.connect():
                return True
        except sa.exc.OperationalError:
            return False

    docker_services.wait_until_responsive(timeout=30.0, pause=0.1, check=try_connect)
    return url


@pytest.fixture(scope="function")
def db(wiki_scripts_database_url: sa.URL) -> Iterator[Database]:
    """
    Return a Database instance bound to the engine fixture.
    """
    # we use the psycopg driver which works sync as well as async
    sync_url = wiki_scripts_database_url
    async_url = wiki_scripts_database_url
    db = Database(sync_url, async_url)
    yield db

    # drop all existing tables
    metadata = sa.MetaData()
    metadata.reflect(bind=db.engine)
    metadata.drop_all(bind=db.engine)
