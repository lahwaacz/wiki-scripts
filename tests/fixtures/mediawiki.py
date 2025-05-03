from typing import Iterator

import httpx
import pytest
import pytest_docker
import sqlalchemy as sa

from ws.client.api import API

__all__ = [
    "mediawiki_service",
    "mediawiki_database_url",
    "mediawiki",
]


def is_responsive(url: str) -> bool:
    try:
        response = httpx.get(url, follow_redirects=True)
        response.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


@pytest.fixture(scope="session")
def mediawiki_service(docker_ip: str, docker_services: pytest_docker.Services) -> str:
    """Ensure that MediaWiki service is up and responsive."""
    # port_for takes a container port and returns the corresponding host port
    port = docker_services.port_for("mediawiki", 80)
    url = f"http://{docker_ip}:{port}"
    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.1, check=lambda: is_responsive(url)
    )
    return url


@pytest.fixture(scope="session")
def mediawiki_database_url(
    containers_dotenv_values: dict[str, str | None],
    docker_ip: str,
    docker_services: pytest_docker.Services,
) -> sa.URL:
    """Ensure that MediaWiki's database is up and responsive."""
    # port_for takes a container port and returns the corresponding host port
    port = docker_services.port_for("database", 5432)
    user = containers_dotenv_values.get("MW_DB_USER")
    password = containers_dotenv_values.get("MW_DB_PASSWORD")
    url = sa.URL.create(
        drivername="postgresql+psycopg",
        username=user,
        password=password,
        host=docker_ip,
        port=port,
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


class MediaWikiFixtureInstance:
    def __init__(
        self,
        url: str,
        user: str,
        password: str,
        db_url: sa.URL,
        db_name: str,
        db_user: str,
    ):
        self.url = url
        self.db_url = db_url
        self.db_name = db_name
        self.db_user = db_user

        # construct the API object for the new user wiki-scripts in the database
        api_url = f"{url}/api.php"
        index_url = f"{url}/index.php"
        self.api = API(api_url, index_url, API.make_session())
        self.api.login(user, password)

        # create a regular database engine
        self.db_engine = sa.create_engine(
            db_url,
            # use NullPool, so that we don't have to recreate the engine when we drop the database
            poolclass=sa.pool.NullPool,
        )

        # create an engine for management operations
        postgres_url = sa.engine.url.URL.create(
            drivername=db_url.drivername,
            username=db_url.username,
            password=db_url.password,
            host=db_url.host,
            port=db_url.port,
            # need to specify a database that always exists and allows connections
            # (the default database does not work because we are dropping and recreating it)
            database="postgres",
        )
        self.db_autocommit_engine = sa.create_engine(
            postgres_url,
            # In the autocommit mode, the DBAPI does not use a transaction under any circumstances
            # (i.e. begin(), commit(), and rollback() are no-ops). This is necessary for operations
            # that drop and create a database.
            # https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#setting-transaction-isolation-levels-dbapi-autocommit
            isolation_level="AUTOCOMMIT",
            # use NullPool, so that we don't have to recreate the engine when we drop the database
            poolclass=sa.pool.NullPool,
        )

        with self.db_autocommit_engine.connect() as conn:
            databases = list(
                conn.execute(sa.text("SELECT datname FROM pg_database")).scalars()
            )
        assert self.db_name in databases

        if self.db_name + "_template" not in databases:
            # assert self.db_name in metadata.tables
            # save the database as a template for self.clear()
            self._drop_database(self.db_name + "_template")
            self._create_database(
                name=self.db_name + "_template", template=self.db_name
            )

    def _drop_database(self, name=None):
        if name is None:
            name = self.db_name

        with self.db_autocommit_engine.connect() as conn:
            # We cannot drop the database while there are connections to it, so we
            # first disallow new connections and terminate all connections to it.
            conn.execute(
                sa.text(
                    f"UPDATE pg_database SET datallowconn=false WHERE datname = '{name}'"
                )
            )
            try:
                conn.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                        f"FROM pg_stat_activity WHERE pg_stat_activity.datname = '{name}'"
                    )
                )
            except sa.exc.OperationalError:
                # the psycopg driver raises an exception when the command terminates the current connection
                pass

        # drop the database in a new transaction
        with self.db_autocommit_engine.connect() as conn:
            conn.execute(sa.text(f"DROP DATABASE IF EXISTS {name}"))
            conn.execute(
                sa.text(
                    f"UPDATE pg_database SET datallowconn=true WHERE datname = '{name}'"
                )
            )

    def _create_database(self, name=None, template=None):
        if name is None:
            name = self.db_name
        if template is None:
            template = self.db_name + "_template"

        with self.db_autocommit_engine.connect() as conn:
            # We cannot create the database while there are connections to the template,
            # so we first disallow new connections and terminate all connections to it.
            conn.execute(
                sa.text(
                    f"UPDATE pg_database SET datallowconn=false WHERE datname = '{template}'"
                )
            )
            try:
                conn.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pg_stat_activity.pid) "
                        f"FROM pg_stat_activity WHERE pg_stat_activity.datname = '{template}'"
                    )
                )
            except sa.exc.OperationalError:
                # the psycopg driver raises an exception when the command terminates the current connection
                pass

        with self.db_autocommit_engine.connect() as conn:
            conn.execute(
                sa.text(
                    f"CREATE DATABASE {name} WITH TEMPLATE {template} OWNER {self.db_user}"
                )
            )
            conn.execute(
                sa.text(
                    f"UPDATE pg_database SET datallowconn=true WHERE datname = '{template}'"
                )
            )

    def clear(self):
        """
        Tests which need the wiki to be in a predictable state should call this
        method to drop all content and then build up what they need.
        """
        # DROP DATABASE is much faster than TRUNCATE on all tables in the database.
        # CREATE DATABASE ... WITH TEMPLATE ... is faster than full re-initialization
        # and as a bonus does not mess up the session cache.
        self._drop_database()
        self._create_database()


# TODO: optimize fixture scope
@pytest.fixture(scope="function")
def mediawiki(
    containers_dotenv_values: dict[str, str | None],
    mediawiki_service: str,
    mediawiki_database_url: sa.URL,
) -> Iterator[MediaWikiFixtureInstance]:
    user = containers_dotenv_values.get("MW_USER")
    password = containers_dotenv_values.get("MW_PASSWORD")
    db_name = containers_dotenv_values.get("MW_DB_NAME")
    db_user = containers_dotenv_values.get("MW_DB_USER")
    assert user
    assert password
    assert db_name
    assert db_user
    instance = MediaWikiFixtureInstance(
        mediawiki_service, user, password, mediawiki_database_url, db_name, db_user
    )
    yield instance
    instance.clear()
