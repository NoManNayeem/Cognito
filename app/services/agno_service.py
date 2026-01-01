"""Agno service for agent initialization and management."""
import uuid
import logging
import asyncpg
from typing import Optional
from app.config import settings
from app.services.knowledge_service import get_knowledge_service

# Configure logging
logger = logging.getLogger(__name__)

# Try to import Agno components
try:
    from agno.agent import Agent
    from agno.db.postgres import AsyncPostgresDb
    from agno.models.openai import OpenAIChat
except ImportError:
    Agent = None
    AsyncPostgresDb = None
    OpenAIChat = None


class AgnoService:
    """Service for managing Agno agents."""
    
    def __init__(self):
        """Initialize Agno service with database connection."""
        if AsyncPostgresDb is None:
            raise ImportError("Agno package not found. Please install agno[all]")
        
        # Initialize PostgreSQL database for Agno (async for FastAPI)
        # Ensure db_url uses async driver (postgresql+asyncpg://)
        db_url = settings.agno_db_url
        # Convert to async format if needed
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgresql+psycopg://"):
            db_url = db_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        elif not db_url.startswith("postgresql+asyncpg://"):
            # If it doesn't start with any known prefix, assume it needs the async prefix
            if "://" not in db_url:
                # If no protocol, assume it's just the connection part
                db_url = f"postgresql+asyncpg://{db_url}"
            else:
                # Unknown protocol, try to convert
                db_url = f"postgresql+asyncpg://{db_url.split('://', 1)[1]}"
        
        self.db = AsyncPostgresDb(db_url=db_url)
        self.knowledge_service = get_knowledge_service()
    
    def create_agent(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Agent:
        """Create a new Agno agent instance.
        
        Args:
            session_id: Optional session ID for conversation continuity
            user_id: Optional user ID for personalized memories
        
        Returns:
            Initialized Agent instance
        """
        # Generate session_id if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        # Create Knowledge instance for agentic RAG (returns None, we use custom tool instead)
        knowledge = self.knowledge_service.create_knowledge()
        
        # Create custom search tool for Cognee
        search_tool = self.knowledge_service.create_search_tool()
        
        # Initialize agent with OpenAI model
        agent_kwargs = {
            "model": OpenAIChat(
                id=settings.llm_model,
                api_key=settings.llm_api_key
            ),
            "db": self.db,
            "session_id": session_id,
            "add_history_to_context": True,  # Enable conversation persistence
            "enable_user_memories": True,     # Enable personalized long-term memory
        }
        
        # Add user_id if provided (for personalized memories)
        if user_id is not None:
            agent_kwargs["user_id"] = str(user_id)
        
        # Add knowledge if available
        if knowledge is not None:
            agent_kwargs["knowledge"] = knowledge
        
        # Add custom search tool for Cognee integration
        tools = []
        if search_tool is not None:
            tools.append(search_tool)
        if tools:
            agent_kwargs["tools"] = tools
        
        agent = Agent(**agent_kwargs)
        
        return agent
    
    async def process_message(
        self,
        message: str,
        session_id: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> dict:
        """Process a user message through an Agno agent.
        
        Args:
            message: User's message
            session_id: Optional session ID for conversation continuity
            user_id: Optional user ID for personalized memories
        
        Returns:
            Dictionary with response and session_id
        """
        # Create agent instance (fast instantiation ~3us)
        agent = self.create_agent(session_id=session_id, user_id=user_id)
        
        # Get the actual session_id from agent
        actual_session_id = agent.session_id
        
        # Process message through agent
        # The agent will autonomously use search_knowledge_base tool when needed
        try:
            response = await agent.arun(message)
            
            # Extract response content
            if hasattr(response, 'content'):
                response_text = response.content
            elif hasattr(response, 'text'):
                response_text = response.text
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)
            
            return {
                "response": response_text,
                "session_id": actual_session_id
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {
                "response": f"Error processing message: {str(e)}",
                "session_id": actual_session_id
            }

    async def get_conversation_stats(self) -> int:
        """Count total conversations/sessions in the Agno database."""
        try:
            # Extract connection details from AGNO_DB_URL
            db_url = settings.agno_db_url
            
            # Remove protocol
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
            
            # Connect to Agno database
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
                    return await conn.fetchval("SELECT COUNT(*) FROM agno_sessions")
                return 0
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"Failed to count conversations: {str(e)}")
            return 0


    async def get_user_sessions(self, user_id: int, limit: int = 50) -> list:
        """List sessions for a specific user."""
        try:
            # Extract connection details from AGNO_DB_URL
            db_url = settings.agno_db_url
            
            # Remove protocol
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
            
            # Connect to Agno database
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
                    return []
                
                # Query sessions for this user
                # Note: Agno stores user_id as string in session_data or metadata
                user_id_str = str(user_id)
                rows = await conn.fetch(
                    """
                    SELECT session_id, created_at, updated_at, session_data, metadata
                    FROM agno_sessions
                    WHERE user_id = $1 OR session_data->>'user_id' = $2 OR metadata->>'user_id' = $2
                    ORDER BY updated_at DESC
                    LIMIT $3
                    """,
                    user_id_str,
                    user_id_str,
                    limit
                )
                
                sessions = []
                for row in rows:
                    sessions.append({
                        "session_id": row["session_id"],
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                    })
                
                return sessions
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"Failed to list sessions: {str(e)}")
            return []


# Global instance
_agno_service: Optional[AgnoService] = None


def get_agno_service() -> AgnoService:
    """Get or create Agno service instance.
    
    Note: This will raise an exception if Agno cannot be initialized.
    The service should be initialized lazily when first needed.
    """
    global _agno_service
    if _agno_service is None:
        try:
            _agno_service = AgnoService()
        except Exception as e:
            # Log error but don't fail silently
            logger.warning(f"Failed to initialize Agno service: {str(e)}")
            raise
    return _agno_service
