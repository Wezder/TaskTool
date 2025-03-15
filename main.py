from database.database import *
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

app = FastAPI()

class UserCreate(BaseModel):
    name: str
    age: int

class UserUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None

@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(Person).all()

@app.get("/users/{id}")
def get_user(id: int, db: Session = Depends(get_db)):
    person = db.query(Person).get(id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return person

@app.post("/users")
def add_user(user: UserCreate, db: Session = Depends(get_db)):
    person = Person(name=user.name, age=user.age)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person

@app.put("/users/{id}")
def update_user(id: int, user_update: UserUpdate, db: Session = Depends(get_db)):
    person = db.query(Person).get(id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user_update.name is not None:
        person.name = user_update.name
    if user_update.age is not None:
        person.age = user_update.age

    db.commit()
    db.refresh(person)
    return person

@app.delete("/users/{id}")
def delete_user(id: int, db: Session = Depends(get_db)):
    person = db.query(Person).get(id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    db.delete(person)
    db.commit()

    return {"message": "Пользователь успешно удален"}