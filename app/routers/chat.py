"""Chat routes for end-user conversational interface."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas import ChatMessage, ChatResponse
from app.security.dependencies import require_scope, get_current_user
from app.models import User
from app.services.agno_service import get_agno_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def chat(
    message: ChatMessage,
    current_user: User = Depends(require_scope("user"))
):
    """Main conversational endpoint with Agno agent.
    
    Protected with require_scope('user') and automatically checks is_active.
    """
    # Check if user is active (already checked in require_scope, but double-check)
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please ask admin to activate account to access features"
        )
    
    # Get Agno service
    try:
        agno_service = get_agno_service()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agno service unavailable: {str(e)}"
        )
    
    # Process message through agent
    try:
        result = await agno_service.process_message(
            message=message.message,
            session_id=message.session_id,
            user_id=current_user.id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )
    
    return ChatResponse(
        response=result["response"],
        session_id=result["session_id"]
    )


@router.get("/sessions")
async def get_sessions(
    current_user: User = Depends(require_scope("user"))
):
    """List user's conversation sessions (optional, for UI)."""
    try:
        import asyncpg
        from app.config import settings
        
        # Extract connection details from AGNO_DB_URL
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
        
        # Connect to Agno database and query sessions
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
            
            if not table_exists:
                return {"sessions": []}
            
            # Query sessions for this user
            # Note: Agno stores user_id as string in session_data or metadata
            user_id_str = str(current_user.id)
            rows = await conn.fetch(
                """
                SELECT session_id, created_at, updated_at, session_data, metadata
                FROM agno_sessions
                WHERE user_id = $1 OR session_data->>'user_id' = $2 OR metadata->>'user_id' = $2
                ORDER BY updated_at DESC
                LIMIT 50
                """,
                user_id_str,
                user_id_str
            )
            
            sessions = []
            for row in rows:
                sessions.append({
                    "session_id": row["session_id"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                })
            
            return {"sessions": sessions}
        finally:
            await conn.close()
    except Exception as e:
        # If querying fails, return empty list (don't fail the request)
        print(f"Warning: Failed to list sessions: {str(e)}")
        return {"sessions": []}
