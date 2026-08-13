"""
`run_migrations()` — Milestone 33 regresyon testi.

Gerçek, ciddi bir prod hatası burada YAKALANDI: Alembic'in `env.py`'si
`fileConfig()`'i varsayılan `disable_existing_loggers=True` ile çağırıyordu
— bu, `run_migrations()`'ın çağrıldığı ANDA zaten var olan (yani pratikte
UYGULAMANIN HER YERİNDEKİ, çünkü FastAPI router'ları startup'tan ÖNCE eager
import edilir) her `logging.getLogger(...)` nesnesini SESSİZCE `.disabled =
True` yapıyordu. Sonuç: core-api'nin İLK migration'ından SONRA, uygulamanın
HİÇBİR yerindeki `logger.info()`/`logger.warning()` çağrısı hiçbir çıktı
ÜRETMİYORDU (istisna da fırlatmıyordu — sessizce hiçbir şey yapmıyordu).
`alembic/env.py`'de `disable_existing_loggers=False` ile düzeltildi.
"""
import logging


def test_run_migrations_does_not_disable_pre_existing_application_loggers():
    # `app.application.services.trip_assistant_service`'i (ya da HERHANGİ
    # bir uygulama modülünü) BU testten ÖNCE zaten import edilmiş olarak
    # kabul ediyoruz — tıpkı prod'da FastAPI'nin router'ları eager import
    # etmesi gibi (bkz. bu dosyanın kendi doc yorumu).
    logger = logging.getLogger("app.application.services.trip_assistant_service")
    assert logger.disabled is False  # test suite'in geri kalanı zaten buna güveniyor

    from app.core.migrations import run_migrations
    run_migrations()

    assert logger.disabled is False, (
        "run_migrations() var olan bir uygulama logger'ını DEVRE DIŞI BIRAKTI — "
        "bkz. alembic/env.py'nin fileConfig(disable_existing_loggers=False) çağrısı."
    )


def test_run_migrations_does_not_disable_a_logger_created_after_it_runs():
    # Aynı garanti, YENİ bir logger için de geçerli olmalı (fileConfig
    # çağrısı yalnızca "zaten var olan"ları etkiler, ama regresyona karşı
    # her iki yönü de kilitlemek ucuz).
    from app.core.migrations import run_migrations
    run_migrations()

    logger = logging.getLogger("app.this_is_a_brand_new_test_logger")
    assert logger.disabled is False
