"""FastAPI dependencies for authentication and authorization."""
from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import SecurityScopes
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import User
from app.security.auth import decode_access_token


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token in HTTP-only cookie."""
    import logging
    logger = logging.getLogger(__name__)
    
    token = request.cookies.get("access_token")
    
    if not token:
        logger.debug(f"No access_token cookie found. Available cookies: {list(request.cookies.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    payload = decode_access_token(token)
    
    if payload is None:
        # Token is invalid - could be expired, malformed, or wrong secret key
        logger.warning("JWT token decode failed - token may be expired or invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    user_id: Optional[int] = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return user


def require_scope(required_scope: str):
    """Factory function that returns a dependency requiring a specific scope."""
    def _require_scope(current_user: User = Depends(get_current_user)) -> User:
        """Require specific scope for the current user."""
        if not current_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please ask admin to activate account to access features"
            )
        
        user_scopes: List[str] = current_user.scopes if isinstance(current_user.scopes, list) else []
        
        if required_scope not in user_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required scope: {required_scope}",
                headers={"WWW-Authenticate": f'Bearer scope="{required_scope}"'},
            )
        
        return current_user
    return _require_scope


def require_scopes(
    security_scopes: SecurityScopes,
    current_user: User = Depends(get_current_user)
) -> User:
    """Require specific scope(s) for the current user using SecurityScopes."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please ask admin to activate account to access features"
        )
    
    user_scopes: List[str] = current_user.scopes if isinstance(current_user.scopes, list) else []
    
    for scope in security_scopes.scopes:
        if scope not in user_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions. Required scope: {scope}",
                headers={"WWW-Authenticate": f'Bearer scope="{scope}"'},
            )
    
    return current_user


def require_active(current_user: User = Depends(get_current_user)) -> User:
    """Require the user to be active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please ask admin to activate account to access features"
        )
    return current_user
