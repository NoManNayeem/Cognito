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
        from app.services.agno_service import get_agno_service
        
        try:
            agno_service = get_agno_service()
            sessions = await agno_service.get_user_sessions(current_user.id)
            return {"sessions": sessions}
        except Exception as e:
            # If service fails, return empty list
            print(f"Warning: Failed to list sessions: {str(e)}")
            return {"sessions": []}
            
    except Exception as e:
        print(f"Error in get_sessions: {str(e)}")
        return {"sessions": []}
