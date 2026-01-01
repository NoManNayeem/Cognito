"""Cognee service for knowledge graph management."""
import os
import asyncio
import logging
from typing import Optional, List, Dict, Any
from app.config import settings
from app.utils.file_handler import get_file_preview as get_local_file_preview

# Configure logging
logger = logging.getLogger(__name__)

# Try to import Cognee - handle different possible import paths
try:
    from cognee import Cognee
    from cognee import Client as CogneeClient
    CogneeClient = CogneeClient
except ImportError:
    try:
        from cognee import Client as CogneeClient
        Cognee = None
        CogneeClient = CogneeClient
    except ImportError:
        try:
            from cognee_sdk import cogwit, CogwitConfig
            Cognee = None
            CogneeClient = None
            cogwit = cogwit
        except ImportError:
            Cognee = None
            CogneeClient = None
            cogwit = None


class CogneeService:
    """Service for interacting with Cognee API/SDK."""
    
    def __init__(self):
        """Initialize Cognee with configuration from environment variables."""
        # Validate required settings
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY is required for Cognee initialization")
        if not settings.db_url:
            raise ValueError("DB_URL is required for Cognee initialization")
        
        # Set environment variables for Cognee
        os.environ["LLM_API_KEY"] = settings.llm_api_key
        os.environ["LLM_PROVIDER"] = settings.llm_provider
        os.environ["LLM_MODEL"] = settings.llm_model
        os.environ["DB_PROVIDER"] = settings.db_provider
        os.environ["DB_URL"] = settings.db_url
        os.environ["GRAPH_DATABASE_PROVIDER"] = settings.graph_database_provider
        os.environ["VECTOR_DB_PROVIDER"] = settings.vector_db_provider
        os.environ["REQUIRE_AUTH"] = settings.require_auth
        os.environ["ALLOW_HTTP_REQUESTS"] = settings.allow_http_requests
        
        # Initialize Cognee instance
        try:
            # Try CogneeClient first (newer API)
            if CogneeClient is not None:
                try:
                    self.cognee = CogneeClient()
                    self.use_cogwit = False
                except Exception as e:
                    # Fallback to Cognee() if Client() doesn't work
                    if Cognee is not None:
                        try:
                            self.cognee = Cognee()
                            self.use_cogwit = False
                        except Exception as e2:
                            raise RuntimeError(f"Failed to initialize Cognee: {str(e2)}")
                    else:
                        raise RuntimeError(f"Failed to initialize Cognee Client: {str(e)}")
            # Try Cognee() (older API)
            elif Cognee is not None:
                try:
                    self.cognee = Cognee()
                    self.use_cogwit = False
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize Cognee: {str(e)}")
            # Try cogwit (alternative SDK)
            elif cogwit is not None:
                try:
                    cogwit_config = CogwitConfig(api_key=settings.llm_api_key)
                    self.cognee = cogwit(cogwit_config)
                    self.use_cogwit = True
                except Exception as e:
                    raise RuntimeError(f"Failed to initialize Cognee (cogwit): {str(e)}")
            else:
                self.cognee = None
                self.use_cogwit = False
                raise ImportError("Cognee package not found. Please install cognee[ollama]")
        except ImportError:
            raise
        except Exception as e:
            raise RuntimeError(f"Cognee initialization error: {str(e)}")
    
    async def add_file(self, dataset_name: str, file_path: str) -> Dict[str, Any]:
        """Add a file to a dataset."""
        if self.cognee is None:
            return {"status": "error", "error": "Cognee not initialized"}
        
        try:
            from pathlib import Path
            if not os.path.exists(file_path):
                return {"status": "error", "error": f"File not found: {file_path}"}
            
            result = await self.cognee.add(
                data=Path(file_path),
                dataset_name=dataset_name,
            )
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error adding file: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def add_url(self, dataset_name: str, url: str) -> Dict[str, Any]:
        """Add a URL to a dataset."""
        try:
            result = await self.cognee.add(
                data=url,
                dataset_name=dataset_name,
            )
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error adding URL: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def cognify(self, dataset_name: str) -> Dict[str, Any]:
        """Trigger knowledge graph creation for a dataset."""
        if self.cognee is None:
            return {"status": "error", "error": "Cognee not initialized"}
        
        try:
            result = await self.cognee.cognify(dataset_names=[dataset_name])
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error cognifying: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def memify(self, dataset_name: str) -> Dict[str, Any]:
        """Optional memory optimization for a dataset."""
        try:
            result = await self.cognee.memify(dataset_names=[dataset_name])
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error memifying: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def get_dataset_data(self, dataset_name: str) -> Dict[str, Any]:
        """Get data from a dataset."""
        try:
            result = await self.cognee.get_dataset_data(dataset_name=dataset_name)
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error getting dataset data: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}

    async def list_files(self, dataset_name: str = "default") -> List[Dict[str, str]]:
        """List all files in a dataset."""
        result = await self.get_dataset_data(dataset_name)
        
        if result["status"] == "error":
            logger.error(f"Failed to list files: {result.get('error')}")
            return []
        
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
        return files

    async def list_urls(self, dataset_name: str = "default") -> List[Dict[str, str]]:
        """List all URLs in a dataset."""
        result = await self.get_dataset_data(dataset_name)
        
        if result["status"] == "error":
            logger.error(f"Failed to list URLs: {result.get('error')}")
            return []
        
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
        return urls

    async def get_file_preview(self, file_id: str, dataset_name: str = "default") -> Optional[str]:
        """Get file preview content."""
        result = await self.get_dataset_data(dataset_name)
        
        if result["status"] == "success" and result.get("data"):
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
                                return get_local_file_preview(file_path)
                            # If file path not found, try to get content from Cognee
                            content = item.get("content") or item.get("text", "")
                            if content:
                                return content[:1000] + ("..." if len(content) > 1000 else "")
        
        # Fallback: Check if file exists in uploads directory
        uploads_dir = "app/static/uploads"
        file_path = os.path.join(uploads_dir, file_id)
        
        if os.path.exists(file_path):
            return get_local_file_preview(file_path)
            
        return None
    
    async def delete_data(self, dataset_name: str, data_id: str) -> Dict[str, Any]:
        """Delete data from a dataset."""
        if self.cognee is None:
            return {"status": "error", "error": "Cognee not initialized"}
        
        try:
            result = await self.cognee.delete_data(dataset_name=dataset_name, data_id=data_id)
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error deleting data: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def search(
        self,
        query: str,
        search_type: str = "GRAPH_COMPLETION"
    ) -> Dict[str, Any]:
        """Search the knowledge base."""
        try:
            if self.cognee is None:
                return {"status": "error", "error": "Cognee not initialized"}
            
            # Try to get SearchType enum
            try:
                from cognee.primitives import SearchType
                search_type_map = {
                    "GRAPH_COMPLETION": SearchType.GRAPH_COMPLETION,
                    "CHUNKS": SearchType.CHUNKS,
                    "SUMMARIES": SearchType.SUMMARIES,
                }
                search_type_enum = search_type_map.get(search_type, SearchType.GRAPH_COMPLETION)
            except (ImportError, AttributeError):
                # Fallback if SearchType not available
                search_type_enum = search_type
            
            if self.use_cogwit:
                result = await self.cognee.search(
                    query_text=query,
                    query_type=search_type_enum,
                )
            else:
                result = await self.cognee.search(
                    query_text=query,
                    query_type=search_type_enum,
                )
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Error searching: {str(e)}", exc_info=True)
            return {"status": "error", "error": str(e)}


# Global instance
_cognee_service: Optional[CogneeService] = None


def get_cognee_service() -> CogneeService:
    """Get or create Cognee service instance.
    
    Note: This will raise an exception if Cognee cannot be initialized.
    The service should be initialized lazily when first needed.
    """
    global _cognee_service
    if _cognee_service is None:
        try:
            _cognee_service = CogneeService()
        except Exception as e:
            # Log error but don't fail silently
            logger.warning(f"Failed to initialize Cognee service: {str(e)}")
            raise
    return _cognee_service
