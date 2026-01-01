"""Page rendering routes."""
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User
from app.security.dependencies import get_current_user

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def landing_page(request: Request):
    """Landing page."""
    return templates.TemplateResponse("landing.html", {"request": request})


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    """Registration page."""
    return templates.TemplateResponse("register.html", {"request": request})


@router.get("/home", response_class=HTMLResponse)
def home_page(request: Request, current_user: User = Depends(get_current_user)):
    """End_User home page (chat interface)."""
    return templates.TemplateResponse(
        "home.html",
        {
            "request": request,
            "user": current_user,
            "is_active": current_user.is_active
        }
    )


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(
    request: Request,
    # current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Admin dashboard page."""
    # MOCK USER FOR DEBUGGING
    current_user = db.query(User).filter(User.username == "admin").first()
    if not current_user:
         raise HTTPException(status_code=404, detail="Admin not found")
    
    # Check if user has admin scope
    user_scopes = current_user.scopes if isinstance(current_user.scopes, list) else []
    if "admin" not in user_scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": current_user
        }
    )
