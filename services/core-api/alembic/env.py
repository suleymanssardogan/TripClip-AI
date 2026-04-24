from logging.config import fileConfig
import os
from dotenv import load_dotenv

from sqlalchemy import engine_from_config, pool
from alembic import context

# .env dosyasını yükle (local geliştirme)
load_dotenv()

# Alembic Config nesnesi
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL'yi ortam değişkeninden al —
# alembic.ini içindeki placeholder'ı override eder
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Modellerin metadata'sı — autogenerate için zorunlu
from app.core.database import Base  # noqa: E402
import app.models.user   # noqa: E402, F401  ← tabloları kayıt et
import app.models.video  # noqa: E402, F401
import app.models.plan   # noqa: E402, F401

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline mod: DB bağlantısı olmadan SQL script üretir."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online mod: gerçek DB bağlantısıyla migration çalıştırır."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
