from fastapi import FastAPI, HTTPException, Depends
from app.services.auth import create_access_token
from app.services.crud import create_user, get_user, send_partner_request
from app.schemas import UserCreate, UserLogin

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
def send_partner_request_endpoint(request: dict):
    UserID = request.get("UserID")
    PartnerID = request.get("PartnerID")
    
    if not get_user(UserID) or not get_user(PartnerID):
        raise HTTPException(status_code=400, detail="Invalid user or partner ID")

    result = send_partner_request(UserID, PartnerID)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {"message": result["message"]}