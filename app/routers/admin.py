"""Admin routes for knowledge management and user administration."""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.security import SecurityScopes
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from pydantic import BaseModel
from app.database import get_db
from app.models import User
from app.schemas import StatsResponse
from app.security.dependencies import require_scope, get_current_user, require_scopes
from app.services.cognee_service import get_cognee_service
from app.services.agno_service import get_agno_service
from app.utils.file_handler import validate_file, save_uploaded_file, get_file_preview
import os
import aiofiles
import asyncpg
from app.config import settings


class URLRequest(BaseModel):
    """Request schema for adding URL."""
    url: str
    dataset_name: str = "default"

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_user: User = Depends(require_scope("admin")),
    db: Session = Depends(get_db)
):
    """Get statistics for admin dashboard."""
    # Count users
    total_users = db.query(User).count()
    
    # Count conversations from Agno database
    total_conversations = 0
    try:
        # Extract connection details from AGNO_DB_URL
        # Format: postgresql+psycopg://user:pass@host:port/dbname
        db_url = settings.agno_db_url
        # Remove postgresql+psycopg:// or postgresql:// prefix
        if "://" in db_url:
            db_url = db_url.split("://", 1)[1]
        
        # Parse connection string
        if "@" in db_url:
            auth, rest = db_url.split("@", 1)
            user, password = auth.split(":", 1) if ":" in auth else (auth, "")
            if "/" in rest:
                host_port, dbname = rest.split("/", 1)
                host, port = host_port.split(":") if ":" in host_port else (host_port, "5432")
            else:
                host, port = rest.split(":") if ":" in rest else (rest, "5432")
                dbname = ""
        else:
            user, password, host, port, dbname = "", "", "localhost", "5432", ""
        
        # Connect to Agno database and count sessions
        conn = await asyncpg.connect(
            user=user,
            password=password,
            host=host,
            port=int(port),
            database=dbname
        )
        try:
            # Check if agno_sessions table exists
            table_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'agno_sessions')"
            )
            if table_exists:
                total_conversations = await conn.fetchval("SELECT COUNT(*) FROM agno_sessions")
        finally:
            await conn.close()
    except Exception as e:
        # If counting fails, log but don't fail the request
        print(f"Warning: Failed to count conversations: {str(e)}")
        total_conversations = 0
    
    # Count files and URLs from Cognee datasets
    total_files = 0
    total_urls = 0
    try:
        try:
            cognee_service = get_cognee_service()
        except Exception as e:
            # If Cognee service is not available, skip file/URL counting
            print(f"Warning: Cognee service unavailable: {str(e)}")
            cognee_service = None
        
        if cognee_service:
            result = await cognee_service.get_dataset_data("default")
            if result["status"] == "success" and result.get("data"):
                dataset_data = result["data"]
                # Parse dataset data - Cognee returns a list of data items
                if isinstance(dataset_data, list):
                    for item in dataset_data:
                        # Check if item is a file (has file path or is Path object)
                        if isinstance(item, dict):
                            # Check for file indicators
                            if "file_path" in item or "path" in item or "filename" in item:
                                total_files += 1
                            # Check for URL indicators
                            elif "url" in item or "link" in item or (isinstance(item.get("data"), str) and item.get("data", "").startswith("http")):
                                total_urls += 1
                        elif hasattr(item, "__fspath__") or str(item).startswith("/"):
                            # Path object or file path string
                            total_files += 1
                        elif isinstance(item, str) and item.startswith("http"):
                            # URL string
                            total_urls += 1
    except Exception as e:
        # If counting fails, log but don't fail the request
        print(f"Warning: Failed to count files/URLs: {str(e)}")
    
    return StatsResponse(
        total_users=total_users,
        total_conversations=total_conversations,
        total_files=total_files,
        total_urls=total_urls
    )


@router.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Upload a file for processing."""
    # Validate file type
    if not validate_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed: PDF, DOCX, TXT, MD"
        )
    
    # Save file to uploads directory
    file_path = await save_uploaded_file(file)
    
    # Add file to Cognee
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
    
    result = await cognee_service.add_file(dataset_name, file_path)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add file to Cognee: {result.get('error', 'Unknown error')}"
        )
    
    return {
        "message": "File uploaded successfully",
        "file_path": file_path,
        "dataset_name": dataset_name
    }


@router.get("/files")
async def list_files(
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """List all files in a dataset."""
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
    
    result = await cognee_service.get_dataset_data(dataset_name)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dataset data: {result.get('error', 'Unknown error')}"
        )
    
    # Filter files from dataset data
    files = []
    if result.get("data"):
        dataset_data = result["data"]
        if isinstance(dataset_data, list):
            for idx, item in enumerate(dataset_data):
                # Check if item is a file
                if isinstance(item, dict):
                    if "file_path" in item or "path" in item or "filename" in item:
                        files.append({
                            "id": item.get("id", str(idx)),
                            "filename": item.get("filename") or item.get("path") or item.get("file_path", "Unknown"),
                            "type": "file"
                        })
                elif hasattr(item, "__fspath__"):
                    # Path object
                    file_path = str(item)
                    files.append({
                        "id": str(idx),
                        "filename": os.path.basename(file_path),
                        "type": "file"
                    })
                elif isinstance(item, str) and not item.startswith("http"):
                    # File path string (not URL)
                    files.append({
                        "id": str(idx),
                        "filename": os.path.basename(item),
                        "type": "file"
                    })
    
    return {"files": files}


@router.get("/files/{file_id}/preview")
async def preview_file(
    file_id: str,
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Preview file content."""
    try:
        try:
            cognee_service = get_cognee_service()
        except Exception as e:
            # Fallback to local file if Cognee is unavailable
            cognee_service = None
        
        result = None
        if cognee_service:
            result = await cognee_service.get_dataset_data(dataset_name)
        
        if result and result["status"] == "success" and result.get("data"):
            dataset_data = result["data"]
            if isinstance(dataset_data, list):
                # Find the file by ID
                for item in dataset_data:
                    item_id = str(item.get("id", "")) if isinstance(item, dict) else str(item)
                    if item_id == file_id:
                        # Try to get file path from item
                        if isinstance(item, dict):
                            file_path = item.get("file_path") or item.get("path") or item.get("filename", "")
                            if file_path and os.path.exists(file_path):
                                preview = get_file_preview(file_path)
                                return {"preview": preview}
                            # If file path not found, try to get content from Cognee
                            content = item.get("content") or item.get("text", "")
                            if content:
                                return {"preview": content[:1000] + ("..." if len(content) > 1000 else "")}
        
        # Fallback: Check if file exists in uploads directory
        uploads_dir = "app/static/uploads"
        file_path = os.path.join(uploads_dir, file_id)
        
        if os.path.exists(file_path):
            preview = get_file_preview(file_path)
            return {"preview": preview}
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error previewing file: {str(e)}"
        )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Delete a file from dataset."""
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
    
    result = await cognee_service.delete_data(dataset_name, file_id)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {result.get('error', 'Unknown error')}"
        )
    
    return {"message": "File deleted successfully"}


@router.post("/files/{file_id}/process")
async def process_file(
    file_id: str,
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Process a file (cognify)."""
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
    
    result = await cognee_service.cognify(dataset_name)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process file: {result.get('error', 'Unknown error')}"
        )
    
    return {"message": "File processing started", "status": result}


@router.post("/urls")
async def add_url(
    url_request: URLRequest,
    current_user: User = Depends(require_scope("admin"))
):
    """Add a URL to dataset."""
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
    
    result = await cognee_service.add_url(url_request.dataset_name, url_request.url)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add URL: {result.get('error', 'Unknown error')}"
        )
    
    return {"message": "URL added successfully", "dataset_name": url_request.dataset_name}


@router.get("/urls")
async def list_urls(
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """List all URLs in a dataset."""
    cognee_service = get_cognee_service()
    result = await cognee_service.get_dataset_data(dataset_name)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dataset data: {result.get('error', 'Unknown error')}"
        )
    
    # Filter URLs from dataset data
    urls = []
    if result.get("data"):
        dataset_data = result["data"]
        if isinstance(dataset_data, list):
            for idx, item in enumerate(dataset_data):
                # Check if item is a URL
                if isinstance(item, dict):
                    if "url" in item or "link" in item:
                        urls.append({
                            "id": item.get("id", str(idx)),
                            "url": item.get("url") or item.get("link", "Unknown"),
                            "type": "url"
                        })
                    elif isinstance(item.get("data"), str) and item.get("data", "").startswith("http"):
                        urls.append({
                            "id": item.get("id", str(idx)),
                            "url": item["data"],
                            "type": "url"
                        })
                elif isinstance(item, str) and item.startswith("http"):
                    # URL string
                    urls.append({
                        "id": str(idx),
                        "url": item,
                        "type": "url"
                    })
    
    return {"urls": urls}


@router.get("/urls/{url_id}/preview")
async def preview_url(
    url_id: str,
    current_user: User = Depends(require_scope("admin"))
):
    """Preview URL (fetch metadata)."""
    try:
        try:
            cognee_service = get_cognee_service()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Cognee service unavailable: {str(e)}"
            )
        
        result = await cognee_service.get_dataset_data("default")
        
        if result["status"] == "success" and result.get("data"):
            dataset_data = result["data"]
            if isinstance(dataset_data, list):
                for item in dataset_data:
                    item_id = str(item.get("id", "")) if isinstance(item, dict) else str(item)
                    if item_id == url_id:
                        if isinstance(item, dict):
                            url = item.get("url") or item.get("link") or item.get("data", "")
                        elif isinstance(item, str):
                            url = item
                        else:
                            url = str(item)
                        
                        return {
                            "preview": f"URL: {url}\n\nMetadata: {item if isinstance(item, dict) else 'No additional metadata available'}"
                        }
        
        return {"preview": "URL not found in dataset"}
    except Exception as e:
        return {"preview": f"Error fetching URL preview: {str(e)}"}


@router.delete("/urls/{url_id}")
async def delete_url(
    url_id: str,
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Delete a URL from dataset."""
    cognee_service = get_cognee_service()
    result = await cognee_service.delete_data(dataset_name, url_id)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete URL: {result.get('error', 'Unknown error')}"
        )
    
    return {"message": "URL deleted successfully"}


@router.post("/urls/{url_id}/process")
async def process_url(
    url_id: str,
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Process a URL (cognify)."""
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
    
    result = await cognee_service.cognify(dataset_name)
    
    if result["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process URL: {result.get('error', 'Unknown error')}"
        )
    
    return {"message": "URL processing started", "status": result}


@router.get("/users")
async def list_users(
    current_user: User = Depends(require_scope("admin")),
    db: Session = Depends(get_db)
):
    """List all users."""
    users = db.query(User).all()
    return {
        "users": [
            {
                "id": user.id,
                "username": user.username,
                "is_active": user.is_active,
                "scopes": user.scopes,
                "created_at": user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
    }


@router.patch("/users/{user_id}/activate")
async def toggle_user_activation(
    user_id: int,
    current_user: User = Depends(require_scope("admin")),
    db: Session = Depends(get_db)
):
    """Activate or deactivate a user."""
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Toggle activation status
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    
    return {
        "message": f"User {'activated' if user.is_active else 'deactivated'} successfully",
        "user": {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active
        }
    }
