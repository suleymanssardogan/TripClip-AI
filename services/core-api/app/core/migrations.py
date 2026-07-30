"""
Startup'ta Alembic migration'larını uygular.

Birden fazla core-api replica'sı aynı anda ayağa kalkarsa (yatay ölçekleme),
her biri lifespan'de "alembic upgrade head" çalıştırır — bu, aynı şema
üzerinde eşzamanlı DDL'e (CREATE/ALTER TABLE) yol açabilir. Postgres advisory
lock ile bu adım tek bir process'e serileştirilir: diğerleri lock'u bekler,
sonra şemanın zaten head'de olduğunu görüp no-op geçer. SQLite (yerel
geliştirme/test) advisory lock desteklemediği için sadece Postgres'te
uygulanır — tek process'li yerel ortamda zaten race riski yok.
"""
import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger("alembic.startup")

# Sabit bir string'den türetilmiş, uygulamaya özel advisory lock ID'si —
# aynı Postgres cluster'ında başka bir uygulamanın lock'uyla çakışmasın diye.
_MIGRATION_LOCK_ID = int(hashlib.sha256(b"tripclip-alembic-migration-lock").hexdigest(), 16) % (2**63)


def _build_alembic_config():
    from alembic.config import Config as AlembicConfig

    core_api_root = Path(__file__).parent.parent.parent
    cfg = AlembicConfig(str(core_api_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(core_api_root / "alembic"))
    return cfg


def run_migrations() -> None:
    """Alembic migration'larını uygular. Hata durumunda loglar, fırlatmaz (startup'ı bloklamaz)."""
    from alembic import command as alembic_cmd

    database_url = os.getenv("DATABASE_URL", "")

    try:
        if database_url.startswith("postgresql"):
            _run_with_postgres_lock(alembic_cmd)
        else:
            alembic_cmd.upgrade(_build_alembic_config(), "head")
            logger.info("✅ Alembic migration tamamlandı")
    except Exception as exc:
        logger.warning("⚠️ Alembic migration atlandı: %s", exc)


def _run_with_postgres_lock(alembic_cmd) -> None:
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    lock_engine = create_engine(database_url)
    try:
        with lock_engine.connect() as conn:
            # Diğer replica migration'ı bitirene kadar burada bekler (blocking lock).
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": _MIGRATION_LOCK_ID})
            try:
                alembic_cmd.upgrade(_build_alembic_config(), "head")
                logger.info("✅ Alembic migration tamamlandı")
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": _MIGRATION_LOCK_ID})
    finally:
        lock_engine.dispose()
