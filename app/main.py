from fastapi import FastAPI, HTTPException, Depends
from app.services.auth import create_access_token
from app.services.crud import create_user, get_user, send_partner_request, get_partner_requests, accept_partner_request, reject_partner_request
from app.schemas import UserCreate, UserLogin, PartnerRequest, AcceptPartnerRequest, RejectPartnerRequest

app = FastAPI()

@app.get("/")
def read_root():
        return{"message":"Welcome to Movie Suggestion App"}
    
    
@app.post("/register")
def register(user: UserCreate):
    if get_user(user.UserID):
        raise HTTPException(status_code=400, detail="UserID already registered")

    new_user = {
        "UserID": user.UserID,
        "email": user.email,
        "password": user.password,  
    }
    create_user(new_user)
    return {"message": "User registered successfully"}



@app.post("/login")
def login(user: UserLogin):
    try:
        db_user = get_user(user.UserID)
        if not db_user:
            raise HTTPException(status_code=400, detail="Invalid UserID or password")

        if "password" not in db_user or user.password != db_user["password"]:
            raise HTTPException(status_code=400, detail="Invalid UserID or password")

        access_token = create_access_token(data={"sub": user.UserID})
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected error occurred. Please try again later.")


@app.post("/send-partner-request/")
def send_partner_request_endpoint(request: PartnerRequest):
    UserID = request.UserID
    PartnerID = request.PartnerID

    if not get_user(UserID):
        raise HTTPException(status_code=400, detail=f"User with ID {UserID} does not exist")
    if not get_user(PartnerID):
        raise HTTPException(status_code=400, detail=f"User with ID {PartnerID} does not exist")

    result = send_partner_request(UserID, PartnerID)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {"message": result["message"]}



@app.get("/get-partner-requests/{user_id}")
def get_partner_requests_endpoint(user_id: str):
    requests = get_partner_requests(user_id)
    if not requests["received_requests"] and not requests["sent_requests"]:
        raise HTTPException(status_code=404, detail="No partner requests found")
    return requests


@app.post("/accept-partner-request/")
def accept_partner_request_endpoint(request: AcceptPartnerRequest):
    sender_id = request.SenderUserID
    receiver_id = request.ReceiverUserID

    result = accept_partner_request(sender_id, receiver_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"message": result["message"]}

@app.post("/reject-partner-request/")
def reject_partner_request_endpoint(request: RejectPartnerRequest):
    sender_id = request.SenderUserID
    receiver_id = request.ReceiverUserID

    result = reject_partner_request(sender_id, receiver_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return {"message": result["message"]}