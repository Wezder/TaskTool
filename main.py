from database.database import *
from models.models import *
from fastapi import FastAPI
from sqlalchemy.orm import Session
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from bcrypt import hashpw, gensalt, checkpw

app = FastAPI()

@app.get("/")
def root():
    return FileResponse("frontend/index.html")

@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    return db.query(Person).all()

@app.post("/user/login")
def user_login(user_data: UserLogin, db: Session = Depends(get_db)):
    person = db.query(Person).filter(Person.name == user_data.name).first()
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if checkpw(user_data.password.encode(), person.password.encode()):
        return person
    else:
        raise HTTPException(status_code=401, detail="Неверный пароль")

@app.get("/users/{id}")
def get_user(id: int, db: Session = Depends(get_db)):
    person = db.query(Person).get(id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return person

@app.get("/users/{user_id}/tasks", response_model=list[TaskResponse])
def get_tasks(user_id: int, db: Session = Depends(get_db)):
    person = db.query(Person).get(user_id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return person.tasks

@app.post("/user/registration")
def user_registration(user: UserCreate, db: Session = Depends(get_db)):
    hashed_password = hashpw(user.password.encode(), gensalt()).decode('utf-8')
    person = Person(name=user.name, age=user.age, password=hashed_password)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person

@app.post("/users/{user_id}/tasks", response_model=TaskResponse)
def create_task(user_id: int, task: TaskCreate, db: Session = Depends(get_db)):
    person = db.query(Person).get(user_id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    db_task = Task(title=task.title, description=task.description, owner_id=person.id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

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

@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(Task).get(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    if task_update.title is not None:
        db_task.title = task_update.title
    if task_update.description is not None:
        db_task.description = task_update.description
    if task_update.completed is not None:
        db_task.completed = task_update.completed

    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/users/{id}")
def delete_user(id: int, db: Session = Depends(get_db)):
    person = db.query(Person).get(id)
    if not person:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    db.delete(person)
    db.commit()

    return {"message": "Пользователь успешно удален"}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(Task).get(task_id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    db.delete(db_task)
    db.commit()

    return {"message": "Задача успешно удалена"}