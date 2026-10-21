"""Alembic environment. Migrations run as the schema owner role (ASSETA_MIGRATION_DATABASE_URL)."""

import re

from alembic import context
from sqlalchemy import create_engine, pool

import asseta.core.model_registry  # noqa: F401
from asseta.core.config import get_settings
from asseta.core.db import Base

target_metadata = Base.metadata
EXTENSION_TABLES = {"spatial_ref_sys", "geography_columns", "geometry_columns"}
PARTITION_CHILD = re.compile(r"^(machine_position_event|tracker_ingestion_event)_(\d{6}|default)")
RAW_SQL_INDEXES = {"ix_latest_location", "ix_job_site_center", "ix_position_event_time_brin"}


def include_object(obj: object, name: str | None, type_: str, reflected: bool, compare_to: object) -> bool:
    """Exclude extension tables, partition children (managed by ensure_telemetry_partitions) and raw-SQL indexes."""
    if type_ == "table" and name is not None and (name in EXTENSION_TABLES or PARTITION_CHILD.match(name)):
        return False
    if type_ == "index" and name is not None and (name in RAW_SQL_INDEXES or PARTITION_CHILD.match(name)):
        return False
    table = getattr(obj, "table", None)
    return not (type_ == "index" and table is not None and PARTITION_CHILD.match(str(table.name)))


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().migration_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = context.config.attributes.get("url") or get_settings().migration_database_url
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True, include_object=include_object
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
