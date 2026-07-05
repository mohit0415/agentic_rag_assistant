import os
from llama_index.core import SQLDatabase
from sqlalchemy import create_engine
from typing import List,Optional
from ..config.config import load_config

DEFAULT_TABLES = [
    "somatosensory_receptors",
    "receptor_density",
    "pain_signal_types",
    "drug_interactions",
    "lab_reference_ranges",
    "clinical_conditions",
]


def get_db_engine():

    config = load_config()
    db_engine = create_engine(config.get('database_url'))

    return db_engine


def get_sql_database(engine=None, include_tables : Optional[List] = None):
    if engine is None:
        engine_load = get_db_engine()
    else:
        engine_load = engine


    tables_load = []

    if include_tables is not None:
        tables_load.extend(include_tables)
    else:
        env_tables = os.getenv("SQL_INCLUDE_TABLES")
        if env_tables:
            tables_load.extend(t.strip() for t in env_tables.split(",") if t.strip())
        else:
            tables_load.extend(DEFAULT_TABLES)


    sql_database = SQLDatabase(
        engine=engine_load,
        include_tables=tables_load
    )

    return sql_database
