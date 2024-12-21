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
    ws_config_path = os.path.expanduser(config.get_main_option("ws_config_path"))
    parser = ws.config.ConfigParser(ws_config_path)
    conf = parser.fetch_section("alembic", to_list=False)

    db_dialect = conf.get("db-dialect", "postgresql")
    db_driver = conf.get("db-driver", "psycopg")
    db_user = conf["db-user"]
    db_password = conf["db-password"]
    db_host = conf.get("db-host", "localhost")
    db_port = conf.get("db-port")
    db_name = conf["db-name"]

    url = sa.engine.url.URL.create(f"{db_dialect}+{db_driver}",
                                   username=db_user,
                                   password=db_password,
                                   host=db_host,
                                   port=db_port,
                                   database=db_name)
    return url


def my_compare_type(context, inspected_column,
            metadata_column, inspected_type, metadata_type):
    # return False if the metadata_type is the same as the inspected_type
    # or None to allow the default implementation to compare these
    # types. a return value of True means the two types do not
    # match and should result in a type change operation.
    return None
    # TODO: the built-in comparison did not detect VARCHAR -> TEXT change, so I did it manually like this:
#    print(context, inspected_column, metadata_column, repr(inspected_type), repr(metadata_type))
#    if repr(metadata_type) == "UnicodeText()" and repr(inspected_type) != "TEXT()":
#        return True
#    return False


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        # turn on comparing SQL types, see http://alembic.zzzcomputing.com/en/latest/autogenerate.html#compare-types
        compare_type=my_compare_type,
    )

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
            target_metadata=target_metadata,
            # turn on comparing SQL types, see http://alembic.zzzcomputing.com/en/latest/autogenerate.html#compare-types
            compare_type=my_compare_type,
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
