from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel

class Person(BaseModel):
    name: str
    age: int

app = FastAPI()

@app.get("/")
def root():
    return FileResponse("index.html")

@app.post("/init")
def init(person: Person):
    return {"message": f"name, {person.name}, age - {person.age}"}