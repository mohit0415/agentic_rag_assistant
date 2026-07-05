
from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Optional

from sqlalchemy.engine import Engine

from ..config.config import load_config, logger
from .structured_data_db import get_db_engine

_ADVISORY_LOCK_KEY = 918273645

_BOOKKEEPING_DDL = """
CREATE TABLE IF NOT EXISTS schema_bootstrap (
    filename    TEXT PRIMARY KEY,
    checksum    TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "y", "t"}


def _resolve_schema_path() -> Optional[Path]:
    env_path = os.getenv("SCHEMA_SQL_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        return p if p.is_file() else None

    filename = os.getenv("SCHEMA_SQL_FILENAME", "medical_database_schema.sql")
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / filename,   
        here.parents[2] / filename,   
        Path.cwd() / filename,
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_sql_bootstrap(engine: Optional[Engine] = None) -> bool:
    if not _truthy(os.getenv("SQL_BOOTSTRAP_ENABLED", "true")):
        logger.info("SQL bootstrap disabled via SQL_BOOTSTRAP_ENABLED=false — skipping.")
        return False

    schema_path = _resolve_schema_path()
    if schema_path is None:
        logger.warning(
            "SQL bootstrap: no schema file found "
            "(set SCHEMA_SQL_PATH to point at it). Skipping."
        )
        return False

    checksum = _checksum(schema_path)
    filename = schema_path.name
    sql_script = schema_path.read_text()
    eng = engine if engine is not None else get_db_engine()

    raw = eng.raw_connection()
    try:
        cur = raw.cursor()

        cur.execute("SELECT pg_advisory_xact_lock(%s)", (_ADVISORY_LOCK_KEY,))
        cur.execute(_BOOKKEEPING_DDL)

        cur.execute(
            "SELECT checksum FROM schema_bootstrap WHERE filename = %s",
            (filename,),
        )
        row = cur.fetchone()
        existing = row[0] if row else None

        if existing == checksum:
            raw.rollback() 
            logger.info(
                "SQL bootstrap: '%s' already applied (checksum match) — skipping.",
                filename,
            )
            return False

        action = "re-applying (file changed)" if existing else "applying (first run)"
        logger.info("SQL bootstrap: %s '%s'.", action, filename)
        cur.execute(sql_script)

        cur.execute(
            """
            INSERT INTO schema_bootstrap (filename, checksum, applied_at)
            VALUES (%s, %s, now())
            ON CONFLICT (filename)
            DO UPDATE SET checksum = EXCLUDED.checksum, applied_at = now()
            """,
            (filename, checksum),
        )

        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    logger.info("SQL bootstrap: '%s' applied successfully.", filename)
    return True
