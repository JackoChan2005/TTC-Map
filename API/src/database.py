from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import globals

# Use the same connection string your transformer uses
# Note: SQLAlchemy needs the sqlite:/// prefix
SQLALCHEMY_DATABASE_URL = f"sqlite:///{globals.conn}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__name__":
    get_db()