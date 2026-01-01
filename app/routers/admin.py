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
import logging
from app.config import settings

# Configure logging
logger = logging.getLogger(__name__)


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
    
    # Count conversations from Agno database via service
    total_conversations = 0
    try:
        agno_service = get_agno_service()
        total_conversations = await agno_service.get_conversation_stats()
    except Exception as e:
        logger.warning(f"Failed to count conversations: {str(e)}")
        total_conversations = 0
    
    # Count files and URLs from Cognee datasets via service
    total_files = 0
    total_urls = 0
    try:
        try:
            cognee_service = get_cognee_service()
        except Exception as e:
            # If Cognee service is not available, skip file/URL counting
            logger.warning(f"Cognee service unavailable: {str(e)}")
            cognee_service = None
        
        if cognee_service:
            # use list_files and list_urls which do the parsing for us
            files = await cognee_service.list_files("default")
            urls = await cognee_service.list_urls("default")
            total_files = len(files)
            total_urls = len(urls)
            
    except Exception as e:
        # If counting fails, log but don't fail the request
        logger.warning(f"Failed to count files/URLs: {str(e)}")
    
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
    
    files = await cognee_service.list_files(dataset_name)
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
            logger.warning(f"Cognee service unavailable for preview: {str(e)}")
        
        preview = None
        if cognee_service:
            preview = await cognee_service.get_file_preview(file_id, dataset_name)
        
        # Fallback if service returned None (and service was available but couldn't find/read it)
        # However, the service method already handles the local fallback logic too! 
        # So if it returns None, it really is not found.
        # But wait, if cognee_service was None (exception), we need manual fallback here?
        # The service method uses imports that might fail if we can't get the service instance?
        # Actually `get_cognee_service` might raise.
        
        if preview:
            return {"preview": preview}
            
        # If we are here, either service failed or returned None.
        # If service failed (cognee_service is None), we should try manual fallback.
        if cognee_service is None:
             # Fallback: Check if file exists in uploads directory
            uploads_dir = "app/static/uploads"
            file_path = os.path.join(uploads_dir, file_id)
            if os.path.exists(file_path):
                 # We need to import get_file_preview from utils again locally or use the one imported at top
                 from app.utils.file_handler import get_file_preview as get_local_preview
                 return {"preview": get_local_preview(file_path)}
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing file: {str(e)}", exc_info=True)
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
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )
        
    urls = await cognee_service.list_urls(dataset_name)
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
        
        # We can implement get_url_preview in service too, but for now we'll do it here or add it to service?
        # The plan said "get_preview" in service, but I implemented `get_file_preview`.
        # Reuse logic:
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
        logger.error(f"Error fetching URL preview: {str(e)}", exc_info=True)
        return {"preview": f"Error fetching URL preview: {str(e)}"}


@router.delete("/urls/{url_id}")
async def delete_url(
    url_id: str,
    dataset_name: str = "default",
    current_user: User = Depends(require_scope("admin"))
):
    """Delete a URL from dataset."""
    try:
        cognee_service = get_cognee_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Cognee service unavailable: {str(e)}"
        )

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
