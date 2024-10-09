from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# PostgreSQL database URL from .env
DATABASE_URL = settings.POSTGRES_URL
print(DATABASE_URL)

engine = create_engine("postgresql://postgres:1234@localhost:5432/hello")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


