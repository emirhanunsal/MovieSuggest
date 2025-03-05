from jose import JWTError, jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import RedirectResponse
from typing import Optional
from starlette.status import HTTP_401_UNAUTHORIZED
from functools import wraps

load_dotenv()

# Get SECRET_KEY from environment or use default
SECRET_KEY = os.getenv("SECRET_KEY", "your-256-bit-secret-key-moviesuggestion-app-2024")
if not SECRET_KEY:
    print("WARNING: Using default SECRET_KEY. This is not secure for production!")
    SECRET_KEY = "your-256-bit-secret-key-moviesuggestion-app-2024"

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 saat

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    try:
        print(f"Creating access token for data: {data}")
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire})
        print(f"Data to encode: {to_encode}")
        print(f"Using SECRET_KEY: {SECRET_KEY}")
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        print(f"Generated token: {encoded_jwt}")
        return encoded_jwt
    except Exception as e:
        print(f"Error creating access token: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None

async def get_current_user(request: Request):
    credentials_exception = HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Oturum süreniz dolmuş veya geçersiz. Lütfen tekrar giriş yapın.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception
    
    if token.startswith("Bearer "):
        token = token[7:]
    
    user_id = decode_token(token)
    if user_id is None:
        raise credentials_exception
        
    return user_id

def login_required(func):
    """Endpoint'leri korumak için decorator"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        token = request.cookies.get("access_token")
        if not token:
            return RedirectResponse(url="/login", status_code=303)
        
        if token.startswith("Bearer "):
            token = token[7:]
        
        user_id = decode_token(token)
        if not user_id:
            return RedirectResponse(url="/login", status_code=303)
        
        return await func(request, *args, **kwargs)
    
    return wrapper
