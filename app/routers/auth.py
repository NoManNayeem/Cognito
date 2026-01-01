"""Authentication routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserResponse, UserLogin
from app.security.auth import verify_password, get_password_hash, create_access_token
from app.security.dependencies import get_current_user
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user (default: scope='user', inactive)."""
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        hashed_password=hashed_password,
        is_active=False,  # Inactive by default
        scopes=["user"]  # Default scope
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.post("/login")
def login(
    user_data: UserLogin,
    response: Response,
    db: Session = Depends(get_db)
):
    """Authenticate user and set HTTP-only cookie with JWT containing scopes."""
    from fastapi.responses import RedirectResponse, JSONResponse
    
    user = db.query(User).filter(User.username == user_data.username).first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.id, "scopes": user.scopes},
        expires_delta=access_token_expires
    )
    
    # Set HTTP-only cookie with proper attributes
    # secure=False in development (HTTP), secure=True in production (HTTPS)
    # SameSite="lax" allows cookies to be sent on top-level navigations (like redirects)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,  # Prevents JavaScript access (XSS protection)
        secure=settings.cookie_secure,  # True for HTTPS, False for HTTP in dev
        samesite="lax",  # Allows cookie on same-site requests and top-level navigations
        max_age=settings.access_token_expire_minutes * 60,
        path="/",  # Cookie available for all paths
        # domain is not set - defaults to current domain (localhost works)
    )
    
    # Check if this is an AJAX request (from JavaScript fetch)
    # If so, return JSON. Otherwise, redirect server-side
    # We'll check the Accept header or Content-Type
    # For now, always return JSON for API consistency
    # The frontend will handle the redirect
    
    return {
        "message": "Login successful",
        "user": {
            "id": user.id,
            "username": user.username,
            "scopes": user.scopes,
            "is_active": user.is_active
        }
    }


@router.post("/logout")
def logout(response: Response):
    """Clear authentication cookie."""
    from fastapi.responses import RedirectResponse
    response.delete_cookie(
        key="access_token",
        secure=settings.cookie_secure,
        samesite="lax",
        path="/"  # Must match the path used when setting the cookie
    )
    return RedirectResponse(url="/?message=Logged out successfully", status_code=303)


@router.get("/logout")
def logout_get(response: Response):
    """Clear authentication cookie (GET method for direct navigation)."""
    from fastapi.responses import RedirectResponse
    response.delete_cookie(
        key="access_token",
        secure=settings.cookie_secure,
        samesite="lax",
        path="/"  # Must match the path used when setting the cookie
    )
    return RedirectResponse(url="/?message=Logged out successfully", status_code=303)


@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info including scopes."""
    return current_user


@router.get("/check-auth")
def check_auth(request: Request, db: Session = Depends(get_db)):
    """Debug endpoint to check authentication status."""
    token = request.cookies.get("access_token")
    
    if not token:
        return {
            "authenticated": False,
            "reason": "No access_token cookie found",
            "cookies": list(request.cookies.keys())
        }
    
    from app.security.auth import decode_access_token
    payload = decode_access_token(token)
    
    if payload is None:
        return {
            "authenticated": False,
            "reason": "Invalid or expired token",
            "has_token": True
        }
    
    user_id = payload.get("sub")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return {
                "authenticated": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "scopes": user.scopes,
                    "is_active": user.is_active
                }
            }
    
    return {
        "authenticated": False,
        "reason": "User not found",
        "user_id": user_id
    }
