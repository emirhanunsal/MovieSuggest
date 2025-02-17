from fastapi import FastAPI, HTTPException
from app.services.auth import create_access_token
from app.services.crud import create_user, get_user, send_partner_request, get_partner_requests, accept_partner_request, reject_partner_request, get_user_preferences, update_user_preferences, add_to_user_preferences, delete_from_user_preferences, get_combined_preferences
from app.schemas import UserCreate, UserLogin, PartnerRequest, AcceptPartnerRequest, RejectPartnerRequest, UserPreferences, UpdatePreferences
from app.services.openai_integration import generate_details, generate_movie_recommendations

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


@app.get("/preferences/{user_id}", response_model=UserPreferences)
def get_preferences_endpoint(user_id: str):
    # Call the CRUD function to get preferences
    preferences = get_user_preferences(user_id)
    if "error" in preferences:
        raise HTTPException(status_code=404, detail=preferences["error"])
    return preferences

@app.put("/preferences/{user_id}")
def update_preferences_endpoint(user_id: str, updates: UpdatePreferences):
    result = update_user_preferences(user_id, updates.Genre, updates.Movies)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"message": result["message"]}

@app.patch("/preferences/{user_id}/add")
def add_preferences_endpoint(user_id: str, updates: UpdatePreferences):
    result = add_to_user_preferences(user_id, updates.Genre, updates.Movies)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"message": result["message"]}

@app.patch("/preferences/{user_id}/delete")
def delete_preferences_endpoint(user_id: str, updates: UpdatePreferences):
    result = delete_from_user_preferences(user_id, updates.Genre, updates.Movies)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"message": result["message"]}



#------------------OPENAI---------------------

@app.get("/generate-details/")
def get_movie_details(movie_name: str):
    """
    Generate or retrieve a genre and description for a movie.
    """
    result = generate_details(movie_name)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.get("/recommend-movies/")
def recommend_movies(user_id: str, partner_id: str):
    """
    Get movie recommendations based on the preferences of two matched partners.
    """
    try:
        # Get combined preferences
        combined_preferences = get_combined_preferences(user_id, partner_id)

        if not combined_preferences or (not combined_preferences["genres"] and not combined_preferences["movies"]):
            raise HTTPException(status_code=400, detail="No shared preferences found to generate recommendations")

        # Generate movie recommendations
        recommendations = generate_movie_recommendations(combined_preferences)
        return {"recommendations": recommendations}

    except Exception as e:
        print(f"Error in recommend_movies: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while generating recommendations")
