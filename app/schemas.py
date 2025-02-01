from pydantic import BaseModel

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