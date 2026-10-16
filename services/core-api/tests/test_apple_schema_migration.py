from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def test_apple_migration_preserves_existing_accounts(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'apple-migration.db'}"
    monkeypatch.setenv('DATABASE_URL', url)
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text('CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR NOT NULL)'))
        db.execute(text("INSERT INTO users (id, email) VALUES (1, 'existing@example.test')"))
    cfg = Config('alembic.ini')
    cfg.set_main_option('sqlalchemy.url', url)
    command.stamp(cfg, 'a81d5c02ef49')
    command.upgrade(cfg, 'head')
    assert 'apple_revocations' in inspect(engine).get_table_names()
    assert 'apple_refresh_token_encrypted' in {c['name'] for c in inspect(engine).get_columns('users')}
    with engine.connect() as db:
        assert db.execute(text('SELECT email, apple_refresh_token_encrypted FROM users')).one() == ('existing@example.test', None)
    command.downgrade(cfg, 'a81d5c02ef49')
    assert 'apple_revocations' not in inspect(engine).get_table_names()
    with engine.connect() as db:
        assert db.execute(text('SELECT email FROM users')).scalar() == 'existing@example.test'
    engine.dispose()
