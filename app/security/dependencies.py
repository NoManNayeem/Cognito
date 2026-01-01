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
    print(f"DEBUG AUTH: token found: {token is not None}")
    
    if not token:
        print(f"DEBUG AUTH: No access_token cookie found. Cookies keys: {list(request.cookies.keys())}")
        logger.error(f"No access_token cookie found in request. Available cookies: {list(request.cookies.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    payload = decode_access_token(token)
    print(f"DEBUG AUTH: payload decoded: {payload is not None}")
    
    if payload is None:
        # Token is invalid - could be expired, malformed, or wrong secret key
        print("DEBUG AUTH: JWT token decode failed")
        logger.error("JWT token decode failed - token may be expired or invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    user_id = payload.get("sub")
    print(f"DEBUG AUTH: user_id from sub: {user_id}")
    if user_id is None:
        logger.error(f"JWT payload missing 'sub' claim: {payload}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    # Cast user_id to int to be safe (JWT subs are often strings)
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        logger.error(f"JWT 'sub' claim is not a valid integer: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    user = db.query(User).filter(User.id == user_id_int).first()
    if user is None:
        logger.error(f"User with ID {user_id_int} not found in database")
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
