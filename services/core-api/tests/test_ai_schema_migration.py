from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from app.core.database import Base


def test_upgrade_and_downgrade_ai_schema_from_existing_head(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    engine = create_engine(url)
    added = {"deferred_jobs", "place_knowledge_documents", "privacy_erasure_records", "pending_file_erasures"}
    Base.metadata.create_all(engine, tables=[table for name, table in Base.metadata.tables.items() if name not in added])
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.stamp(cfg, "d4a9c2e6f108")
    command.upgrade(cfg, "e6b9d18a40c2")
    assert (added - {"privacy_erasure_records", "pending_file_erasures"}) <= set(inspect(engine).get_table_names())
    command.downgrade(cfg, "d4a9c2e6f108")
    assert not added.intersection(inspect(engine).get_table_names())
    assert "places" in inspect(engine).get_table_names()
    engine.dispose()
