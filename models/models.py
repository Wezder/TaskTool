from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    name: str
    age: int
    password: str

class UserUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None

class UserLogin(BaseModel):
    name: str
    password: str

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    owner_id: int

    class Config:
        orm_mode = True