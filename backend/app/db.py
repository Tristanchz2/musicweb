from sqlalchemy import text

from app.database import SessionLocal, engine


def check_db_connection():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()