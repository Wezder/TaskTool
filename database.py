from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import  Column, Integer, String, select
 
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autoflush=False, bind=engine)
session = Session(engine)

class Base(DeclarativeBase): pass

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(40))
    age = Column(Integer,)

    def __repr__(self) -> str:
        return f"(id = {self.id!r}, name = {self.name!r}, age = {self.age!r})"

for user in session.scalars(select(Person)):
    print(user)