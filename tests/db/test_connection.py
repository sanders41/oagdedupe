import pytest
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base

db_url = os.environ.get("DATABASE_URL")
engine = create_engine(db_url)
engine.connect()

Session = scoped_session(sessionmaker(bind=engine))
Base = declarative_base()

@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)

def test_connection(db_session):
    res = db_session.query(text("1"))
    assert res.all() == [(1,)]