"""Knowledge service for Agno agent integration with Cognee."""
from typing import Optional
from app.services.cognee_service import get_cognee_service
from app.config import settings

# Try to import Knowledge and tool decorator from Agno
try:
    from agno.knowledge.knowledge import Knowledge
except ImportError:
    try:
        from agno.knowledge import Knowledge
    except ImportError:
        Knowledge = None

try:
    from agno.tools import tool
except ImportError:
    try:
        from agno import tool
    except ImportError:
        tool = None


class KnowledgeService:
    """Service for creating Knowledge instance and tools for Agno agents."""
    
    def __init__(self):
        """Initialize knowledge service."""
        self.cognee_service = get_cognee_service()
    
    def create_knowledge(self):
        """Create a Knowledge instance pointing to Cognee's data stores.
        
        Note: Agno's Knowledge class requires a vector_db parameter.
        Since Cognee manages its own vector store, we return None here.
        Instead, we provide a custom tool for the agent to search Cognee.
        """
        # Return None as Knowledge requires a vector_db
        # and Cognee manages its own stores separately
        # We'll provide a custom tool instead
        return None
    
    def create_search_tool(self):
        """Create a custom tool for searching Cognee knowledge base.
        
        Returns:
            Tool function that can be added to Agno agent
        """
        if tool is None:
            return None
        
        @tool
        async def search_knowledge_base(
            query: str,
            search_type: str = "GRAPH_COMPLETION"
        ) -> str:
            """Search the knowledge base for information.
            
            This tool searches the Cognee knowledge graph and vector store
            to find relevant information based on the query.
            
            Args:
                query: The search query
                search_type: Type of search - GRAPH_COMPLETION (for complex multi-hop questions),
                           CHUNKS (for direct factual retrieval), or SUMMARIES (for overviews)
            
            Returns:
                Search results as a string
            """
            result = await self.cognee_service.search(query, search_type)
            
            if result["status"] == "error":
                return f"Error searching knowledge base: {result.get('error', 'Unknown error')}"
            
            # Format the search results
            data = result.get("data", [])
            if isinstance(data, list):
                if len(data) == 0:
                    return "No results found in the knowledge base."
                # Format results as text
                formatted_results = []
                for idx, item in enumerate(data[:5], 1):  # Limit to top 5 results
                    if isinstance(item, dict):
                        # Extract relevant fields
                        text = item.get("text") or item.get("content") or item.get("summary", "")
                        if text:
                            formatted_results.append(f"Result {idx}:\n{text}")
                    elif isinstance(item, str):
                        formatted_results.append(f"Result {idx}:\n{item}")
                
                return "\n\n".join(formatted_results) if formatted_results else "No relevant content found."
            elif isinstance(data, str):
                return data
            else:
                return str(data)
        
        return search_knowledge_base
    
    async def search_knowledge_base(
        self,
        query: str,
        search_type: str = "GRAPH_COMPLETION"
    ) -> dict:
        """Search the knowledge base using Cognee."""
        return await self.cognee_service.search(query, search_type)


# Global instance
_knowledge_service: Optional[KnowledgeService] = None


def get_knowledge_service() -> KnowledgeService:
    """Get or create Knowledge service instance.
    
    Note: This depends on CogneeService, so Cognee must be initialized first.
    """
    global _knowledge_service
    if _knowledge_service is None:
        try:
            _knowledge_service = KnowledgeService()
        except Exception as e:
            # Log error but don't fail silently
            print(f"Warning: Failed to initialize Knowledge service: {str(e)}")
            raise
    return _knowledge_service
