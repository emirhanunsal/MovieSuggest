from pydantic import BaseModel

class UserCreate(BaseModel):
    UserID: str
    email: str
    password: str

class UserLogin(BaseModel):
    UserID :str
    password: str