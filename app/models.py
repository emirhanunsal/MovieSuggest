from pydantic import BaseModel


class User(BaseModel):
    UserID: str
    email: str
    hashed_password :str