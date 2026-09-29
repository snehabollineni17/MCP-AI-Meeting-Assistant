from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app import config

engine = create_engine(
    config.DATABASE_URL,
    echo=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
