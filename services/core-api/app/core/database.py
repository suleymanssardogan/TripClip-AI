from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

# pool_pre_ping: DB restart/network kesintisi sonrası bayat bağlantıları
# sessizce 500'e düşürmek yerine, kullanılmadan önce test edip yeniler.
# pool_size/max_overflow/pool_recycle SQLite'ın (test ortamı) desteklediği
# argümanlar değil — yalnızca gerçek (Postgres) bağlantılarda uygulanır.
_engine_kwargs = {"pool_pre_ping": True}
if not DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(pool_size=10, max_overflow=20, pool_recycle=1800)

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False,autoflush=False,bind=engine)

Base = declarative_base()

#Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from app.models import user,video

def create_table():
    Base.metadata.create_all(bind=engine)