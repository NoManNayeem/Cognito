"""FastAPI application initialization."""
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, pages, chat, admin
from app.utils.seed import ensure_admin_user
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup logic
    try:
        logger.info("Starting application initialization...")
        logger.info("Ensuring admin user exists and database is pruned...")
        ensure_admin_user()
        logger.info("Application initialization completed successfully")
    except Exception as e:
        logger.error(f"Failed to initialize admin user: {str(e)}", exc_info=True)
        # Don't raise - allow app to start even if admin creation fails
        # (might be due to DB connection issues that will resolve)
    yield
    # Shutdown logic (if needed)


app = FastAPI(
    title="Cognito - Cognitive Memory Application",
    description="Production-ready cognitive memory application with FastAPI, Cognee, and Agno",
    version="0.1.0",
    lifespan=lifespan
)

# Configure CORS - essential for cookie-based authentication
# Even for same-origin, this ensures credentials are handled correctly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],  # Add production origins in production
    allow_credentials=True,  # Critical for cookies to work
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/")
def root():
    """Root endpoint."""
    return {"message": "Cognito API", "version": "0.1.0"}
