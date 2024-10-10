from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.core.config import settings

DATABASE_URL = settings.POSTGRES_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# In your dependencies
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()