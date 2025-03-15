from database import *
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

app = FastAPI()

@app.get("/")
def root():
    return FileResponse("index.html")

@app.get("/users")
def get_people(db: Session = Depends(get_db)):
    return db.query(Person).all()