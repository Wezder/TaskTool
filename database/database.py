from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, relationship, DeclarativeBase
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey

SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autoflush=False, bind=engine)
session = Session(engine)

class Base(DeclarativeBase): pass

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(40))
    age = Column(Integer)
    password = Column(String(30))
    tasks = relationship("Task", back_populates="owner")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100))
    description = Column(String(500))
    completed = Column(Boolean, default=False)
    owner_id = Column(Integer, ForeignKey("people.id"))
    owner = relationship("Person", back_populates="tasks")

class TodoList(Base):
    __tablename__ = "todo_lists"
    id = Column(Integer, primary_key=True, index=True)
    list_name = Column(String(100))
    owner_id = Column(Integer, ForeignKey("people.id"))
    owner = relationship("Person", back_populates="todo_lists")

Person.todo_lists = relationship("TodoList", back_populates="owner")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

Base.metadata.create_all(bind=engine)