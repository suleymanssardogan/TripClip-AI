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
#
# M33: `disable_existing_loggers=False` EKLENDİ — kritik bir prod hatası.
# `fileConfig()`'in Python varsayılanı `disable_existing_loggers=True`'dur:
# alembic.ini'nin `[loggers]` bölümünde adı GEÇMEYEN (yani root/sqlalchemy/
# alembic DIŞINDAKİ) her `logging.getLogger(...)` nesnesini `.disabled = True`
# yapar. Bu dosya (`env.py`), core-api'nin KENDİ `run_migrations()`'ı
# (app/core/migrations.py) tarafından HER startup'ta çağrılır — o ana kadar
# import edilmiş TÜM modüllerin (video_processor, gemini_service,
# rag_service, trip_assistant_service, vb. — pratikte HEPSİ, çünkü FastAPI
# router'ları startup'tan ÖNCE eager import edilir) logger'ları BU ANDA
# ZATEN var. Sonuç: ilk migration'dan SONRA `logger.info()`/`logger.warning()`
# çağrıları UYGULAMANIN HER YERİNDE sessizce hiçbir şey YAPMAZ (istisna
# fırlatmaz, sadece log ASLA görünmez) — bkz. docs/trip-assistant.md
# "Observability" (M33'ün kendi yeni yapılandırılmış logu da dahil, bu
# olmadan PROD'da HİÇ görünmezdi). Gerçek bir Python sürecinde doğrulandı:
# `logger.disabled` bu satır olmadan `run_migrations()`'tan SONRA `True`
# oluyordu.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# DATABASE_URL'yi ortam değişkeninden al —
# alembic.ini içindeki placeholder'ı override eder
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Modellerin metadata'sı — autogenerate için zorunlu
from app.core.database import Base  # noqa: E402
import app.models.user           # noqa: E402, F401  ← tabloları kayıt et
import app.models.video          # noqa: E402, F401
import app.models.plan           # noqa: E402, F401
import app.models.refresh_token  # noqa: E402, F401
import app.models.password_reset_token  # noqa: E402, F401
import app.models.place          # noqa: E402, F401
import app.models.place_save     # noqa: E402, F401
import app.models.trip           # noqa: E402, F401
import app.models.trip_stop      # noqa: E402, F401
import app.models.trip_share     # noqa: E402, F401
import app.models.share_token    # noqa: E402, F401
import app.models.trip_collaborator  # noqa: E402, F401
import app.models.trip_itinerary      # noqa: E402, F401
import app.models.trip_itinerary_stop # noqa: E402, F401

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
