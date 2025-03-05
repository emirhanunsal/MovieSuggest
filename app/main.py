from fastapi import FastAPI, HTTPException, Request, Form, Depends, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from app.services.auth import create_access_token, get_current_user, login_required
from app.services.crud import create_user, get_user, send_partner_request, get_partner_requests, accept_partner_request, reject_partner_request, get_user_preferences, update_user_preferences, add_to_user_preferences, delete_from_user_preferences, get_combined_preferences, delete_partner, get_notifications, mark_notification_as_read
from app.schemas import UserCreate, UserLogin, PartnerRequest, AcceptPartnerRequest, RejectPartnerRequest, UserPreferences, UpdatePreferences
from app.services.openai_integration import generate_details, generate_movie_recommendations, generate_movie_details_async
from pathlib import Path
from typing import Optional
from functools import wraps
import boto3
import os
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

app = FastAPI()

# Template ve static dosyaların yollarını ayarlayalım
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# DynamoDB bağlantısı
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv("AWS_DEFAULT_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

async def count_unread_notifications(user_id: str) -> int:
    try:
        notifications = get_notifications(user_id)
        return len([n for n in notifications if not n.get("IsRead", False)])
    except Exception:
        return 0

@app.get("/", response_class=HTMLResponse)
@login_required
async def home(request: Request, current_user: str = Depends(get_current_user)):
    try:
        unread_count = await count_unread_notifications(current_user)
        return templates.TemplateResponse(
            "base.html", 
            {
                "request": request,
                "unread_notifications": unread_count,
                "current_user": current_user
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "base.html",
            {"request": request, "error": "Sayfa yüklenirken bir hata oluştu"}
        )

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/preferences")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    UserID: str = Form(...),
    password: str = Form(...)
):
    try:
        print(f"Login attempt for user: {UserID}")
        print(f"Received password: {password}")
        
        # Form verilerini kontrol et
        form_data = await request.form()
        print(f"Form data: {form_data}")
        
        # DynamoDB bağlantısını kontrol et
        print(f"AWS Region: {os.getenv('AWS_DEFAULT_REGION')}")
        print(f"AWS Access Key ID: {os.getenv('AWS_ACCESS_KEY_ID')}")
        print(f"AWS Secret Key exists: {'Yes' if os.getenv('AWS_SECRET_ACCESS_KEY') else 'No'}")
        
        user = get_user(UserID)
        print(f"get_user result: {user}")
        
        if not user:
            print(f"User not found: {UserID}")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Geçersiz kullanıcı ID veya şifre"}
            )
            
        if user.get("password") != password:
            print(f"Invalid password for user: {UserID}")
            print(f"Expected password: {user.get('password')}")
            print(f"Received password: {password}")
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Geçersiz kullanıcı ID veya şifre"}
            )
        
        access_token = create_access_token(data={"sub": UserID})
        response = RedirectResponse(url="/preferences", status_code=303)
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=60 * 60 * 24,  # 24 saat
            samesite="lax"
        )
        print(f"Successful login for user: {UserID}")
        return response
    except Exception as e:
        print(f"Login error for user {UserID}: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Giriş yapılırken bir hata oluştu"}
        )

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    if request.cookies.get("access_token"):
        return RedirectResponse(url="/preferences")
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register", response_class=HTMLResponse)
async def register_post(
    request: Request,
    UserID: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        if get_user(UserID):
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Bu kullanıcı ID zaten kayıtlı"}
            )

        new_user = {
            "UserID": UserID,
            "email": email,
            "password": password
        }
        create_user(new_user)

        # Kullanıcı tercihleri için boş bir kayıt oluştur
        preferences_table = dynamodb.Table('UserPreferences')
        preferences_table.put_item(Item={
            "UserID": UserID,
            "Movies": [],
            "Genre": []
        })

        return RedirectResponse(url="/login", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "error": "Kayıt olurken bir hata oluştu"}
        )

@app.get("/add-partner", response_class=HTMLResponse)
@login_required
async def add_partner_page(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        unread_count = await count_unread_notifications(current_user)
        return templates.TemplateResponse(
            "add_partner.html",
            {
                "request": request,
                "unread_notifications": unread_count,
                "current_user": current_user
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "add_partner.html",
            {"request": request, "error": "Sayfa yüklenirken bir hata oluştu"}
        )

@app.post("/send-partner-request", response_class=HTMLResponse)
@login_required
async def send_partner_request_endpoint(
    request: Request,
    PartnerID: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = send_partner_request(current_user, PartnerID)
        if "error" in result:
            return templates.TemplateResponse(
                "add_partner.html",
                {"request": request, "error": result["error"]}
            )
        return templates.TemplateResponse(
            "add_partner.html",
            {"request": request, "success": "Partner isteği başarıyla gönderildi"}
        )
    except Exception as e:
        return templates.TemplateResponse(
            "add_partner.html",
            {"request": request, "error": "İstek gönderilirken bir hata oluştu"}
        )

@app.get("/partner-requests", response_class=HTMLResponse)
@login_required
async def partner_requests_page(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        requests = get_partner_requests(current_user)
        unread_count = await count_unread_notifications(current_user)
        
        return templates.TemplateResponse(
            "partner_requests.html",
            {
                "request": request,
                "received_requests": requests.get("received_requests", []),
                "sent_requests": requests.get("sent_requests", []),
                "unread_notifications": unread_count,
                "current_user": current_user
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partner_requests.html",
            {"request": request, "error": "Partner istekleri alınırken bir hata oluştu"}
        )

@app.post("/accept-partner-request", response_class=HTMLResponse)
@login_required
async def accept_partner_request_endpoint(
    request: Request,
    SenderUserID: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = accept_partner_request(SenderUserID, current_user)
        if "error" in result:
            return templates.TemplateResponse(
                "partner_requests.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/partner-requests", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "partner_requests.html",
            {"request": request, "error": "İstek kabul edilirken bir hata oluştu"}
        )

@app.post("/reject-partner-request", response_class=HTMLResponse)
@login_required
async def reject_partner_request_endpoint(
    request: Request,
    SenderUserID: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = reject_partner_request(SenderUserID, current_user)
        if "error" in result:
            return templates.TemplateResponse(
                "partner_requests.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/partner-requests", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "partner_requests.html",
            {"request": request, "error": "İstek reddedilirken bir hata oluştu"}
        )

@app.get("/preferences", response_class=HTMLResponse)
@login_required
async def preferences_page(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        # Kullanıcı tercihlerini al
        preferences = get_user_preferences(current_user)
        
        # Partner bilgisini al
        user_data = get_user(current_user)
        partner_id = user_data.get("partner_id") if user_data else None
        
        # Okunmamış bildirim sayısını al
        unread_count = await count_unread_notifications(current_user)

        return templates.TemplateResponse(
            "preferences.html",
            {
                "request": request,
                "preferences": preferences,
                "partner": partner_id,
                "unread_notifications": unread_count,
                "current_user": current_user
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "preferences.html",
            {"request": request, "error": "Tercihler alınırken bir hata oluştu"}
        )

@app.post("/preferences/add-movie", response_class=HTMLResponse)
@login_required
async def add_movie(
    request: Request,
    movie: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = add_to_user_preferences(
            current_user,
            [],  # Boş tür listesi
            [movie]  # Sadece film
        )
        if "error" in result:
            return templates.TemplateResponse(
                "preferences.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/preferences", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "preferences.html",
            {"request": request, "error": "Film eklenirken bir hata oluştu"}
        )

@app.post("/preferences/add-genre", response_class=HTMLResponse)
@login_required
async def add_genre(
    request: Request,
    genre: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = add_to_user_preferences(
            current_user,
            [genre],  # Sadece tür
            []  # Boş film listesi
        )
        if "error" in result:
            return templates.TemplateResponse(
                "preferences.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/preferences", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "preferences.html",
            {"request": request, "error": "Tür eklenirken bir hata oluştu"}
        )

@app.post("/preferences/delete-movie", response_class=HTMLResponse)
@login_required
async def delete_movie(
    request: Request,
    movie: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = delete_from_user_preferences(
            current_user,
            [],  # Boş tür listesi
            [movie]  # Sadece film
        )
        if "error" in result:
            return templates.TemplateResponse(
                "preferences.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/preferences", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "preferences.html",
            {"request": request, "error": "Film silinirken bir hata oluştu"}
        )

@app.post("/preferences/delete-genre", response_class=HTMLResponse)
@login_required
async def delete_genre(
    request: Request,
    genre: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = delete_from_user_preferences(
            current_user,
            [genre],  # Sadece tür
            []  # Boş film listesi
        )
        if "error" in result:
            return templates.TemplateResponse(
                "preferences.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/preferences", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "preferences.html",
            {"request": request, "error": "Tür silinirken bir hata oluştu"}
        )

@app.get("/recommendations", response_class=HTMLResponse)
@login_required
async def recommendations_page(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        # Partner bilgisini al
        user_data = get_user(current_user)
        partner_id = user_data.get("partner_id") if user_data else None
        
        # Okunmamış bildirim sayısını al
        unread_count = await count_unread_notifications(current_user)
        
        return templates.TemplateResponse(
            "recommendations.html",
            {
                "request": request,
                "partner": partner_id,
                "unread_notifications": unread_count,
                "current_user": current_user
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "recommendations.html",
            {"request": request, "error": "Öneriler alınırken bir hata oluştu"}
        )

@app.post("/generate-recommendations", response_class=HTMLResponse)
@login_required
async def generate_recommendations_endpoint(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: str = Depends(get_current_user)
):
    try:
        # Partner bilgisini al
        user_data = get_user(current_user)
        partner_id = user_data.get("partner_id")
        
        if not partner_id:
            return templates.TemplateResponse(
                "recommendations.html",
                {"request": request, "error": "Film önerileri için bir partneriniz olması gerekiyor"}
            )

        # /docs/recommendations endpoint'ini kullanarak öneriler oluştur
        recommendations = await test_recommendations(current_user, partner_id)
        
        if "error" in recommendations:
            return templates.TemplateResponse(
                "recommendations.html",
                {
                    "request": request,
                    "partner": partner_id,
                    "error": recommendations["error"]
                }
            )

        # Partners tablosuna önerileri kaydet
        partners_table = dynamodb.Table('Partners')
        
        # Her iki kullanıcı için de önerileri kaydet
        for user_id in [current_user, partner_id]:
            response = partners_table.scan(
                FilterExpression="UserID = :user_id",
                ExpressionAttributeValues={":user_id": user_id}
            )
            
            if response.get("Items"):
                partner_data = response["Items"][0]
                existing_movies = partner_data.get("Movies", [])
                # Yeni önerileri başa ekle
                new_movies = [movie["title"] for movie in recommendations.get("recommendations", [])]
                all_movies = new_movies + existing_movies
                
                # Update the movies in the table as a list, not a set
                partners_table.update_item(
                    Key={"UserID": user_id},
                    UpdateExpression="SET Movies = :movies",
                    ExpressionAttributeValues={":movies": all_movies}
                )

        # Film detaylarını arka planda oluştur ve database'e kaydet
        movies_table = dynamodb.Table('Movies')
        for movie in recommendations.get("recommendations", []):
            background_tasks.add_task(
                generate_movie_details_async,
                movie["title"],
                movie.get("genres", []),
                movies_table
            )

        return RedirectResponse(url="/recommendations", status_code=303)
    except Exception as e:
        print(f"Error in generate_recommendations_endpoint: {e}")
        return templates.TemplateResponse(
            "recommendations.html",
            {"request": request, "error": "Film önerileri oluşturulurken bir hata oluştu"}
        )

@app.get("/movie-details/{movie_name}")
@login_required
async def movie_details_endpoint(
    request: Request,
    movie_name: str,
    current_user: str = Depends(get_current_user)
):
    try:
        print(f"Getting movie details for: {movie_name}")
        # generate_details fonksiyonu zaten database kontrolü yapıyor
        details = generate_details(movie_name)
        
        if "error" in details:
            print(f"Error getting details for {movie_name}: {details['error']}")
            return JSONResponse(content={"error": "Film detayları alınamadı"})
            
        return JSONResponse(content={
            "description": details.get("description", ""),
            "genres": details.get("genre", [])
        })
    except Exception as e:
        print(f"Error in movie_details_endpoint for {movie_name}: {e}")
        return JSONResponse(content={"error": "Film detayları alınırken bir hata oluştu"})

@app.get("/docs/recommendations")
async def test_recommendations(user1: str, user2: str):
    """
    Test endpoint for movie recommendations.
    Example: /docs/recommendations?user1=User1&user2=User2
    """
    try:
        recommendations = generate_movie_recommendations(user1, user2)
        if not recommendations:
            return {"error": "Film önerileri oluşturulamadı"}
        return {"recommendations": recommendations}
    except Exception as e:
        print(f"Error in test_recommendations: {e}")
        return {"error": "Film önerileri oluşturulurken bir hata oluştu"}

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

@app.post("/delete-partner", response_class=HTMLResponse)
@login_required
async def delete_partner_endpoint(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        result = delete_partner(current_user)
        if "error" in result:
            return templates.TemplateResponse(
                "recommendations.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/recommendations", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "recommendations.html",
            {"request": request, "error": "Partner ilişkisi silinirken bir hata oluştu"}
        )

@app.get("/notifications", response_class=HTMLResponse)
@login_required
async def notifications_page(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    try:
        notifications = get_notifications(current_user)
        unread_count = await count_unread_notifications(current_user)
        
        return templates.TemplateResponse(
            "notifications.html",
            {
                "request": request,
                "notifications": notifications,
                "unread_notifications": unread_count,
                "current_user": current_user
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "notifications.html",
            {"request": request, "error": "Bildirimler alınırken bir hata oluştu"}
        )

@app.post("/mark-notification-read", response_class=HTMLResponse)
@login_required
async def mark_notification_read(
    request: Request,
    timestamp: str = Form(...),
    current_user: str = Depends(get_current_user)
):
    try:
        result = mark_notification_as_read(current_user, timestamp)
        if "error" in result:
            return templates.TemplateResponse(
                "notifications.html",
                {"request": request, "error": result["error"]}
            )
        return RedirectResponse(url="/notifications", status_code=303)
    except Exception as e:
        return templates.TemplateResponse(
            "notifications.html",
            {"request": request, "error": "Bildirim işaretlenirken bir hata oluştu"}
        )
