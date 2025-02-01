from pydantic import BaseModel
from typing import List, Optional

class UserCreate(BaseModel):
    UserID: str
    email: str
    password: str

class UserLogin(BaseModel):
    UserID :str
    password: str

class PartnerRequest(BaseModel):
    UserID: str
    PartnerID: str

class AcceptPartnerRequest(BaseModel):
    SenderUserID: str
    ReceiverUserID: str
    
class RejectPartnerRequest(BaseModel):
    SenderUserID: str
    ReceiverUserID: str

class UserPreferences(BaseModel):
    UserID: str
    Genre: Optional[List[str]] = None
    Movies: Optional[List[str]] = None
    
    
class UpdatePreferences(BaseModel):
    Genre: Optional[List[str]] = None
    Movies: Optional[List[str]] = None
