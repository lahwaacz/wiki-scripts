from __future__ import with_statement
from alembic import context
import logging.config
import sqlalchemy as sa

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
logging.config.fileConfig(config.config_file_name)

# add our project root into the path so that we can import the "ws" module
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "../../.."))

# wiki-scripts' MetaData object for 'autogenerate' support
from ws.db import schema
target_metadata = sa.MetaData()
schema.create_tables(target_metadata)

# get database connection URL from the wiki-scripts config
import ws.config
def get_url():
    ws_config_path = config.get_main_option("ws_config_path")
    f = open(os.path.expanduser(ws_config_path), "r")
    parser = ws.config.ConfigFileParser("site", "alembic")
    conf = parser.parse(f, [])
    
    db_dialect = conf.get("db-dialect", "postgresql")
    db_driver = conf.get("db-driver", "psycopg2")
    db_user = conf["db-user"]
    db_password = conf["db-password"]
    db_host = conf.get("db-host", "localhost")
    db_port = conf.get("db-port")
    db_name = conf["db-name"]

    url = sa.engine.url.URL("{}+{}".format(db_dialect, db_driver),
                            username=db_user,
                            password=db_password,
                            host=db_host,
                            port=db_port,
                            database=db_name)
    return url


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = sa.create_engine(get_url(), poolclass=sa.pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
