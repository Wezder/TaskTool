from database.database import *
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

app = FastAPI()

@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/users")
def get_people(db: Session = Depends(get_db)):
    return db.query(Person).all()

@app.get("/users/{id}")
def get_people(id, db: Session = Depends(get_db)):
    person = db.query(Person).get(id)
    if not person:
        return JSONResponse(status_code=404, content = {'message': 'Пользователь не найден'})
    return person