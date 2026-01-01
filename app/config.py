"""Configuration management for the application."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Configuration
    llm_api_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    
    # Database Configuration
    db_provider: str = "postgresql"
    # Default matches Docker Compose setup: cognito/cognito_password@localhost:5432/cognito
    db_url: str = "postgresql://cognito:cognito_password@localhost:5432/cognito"
    
    # Graph and Vector Store
    graph_database_provider: str = "memgraph"
    vector_db_provider: str = "lancedb"
    
    # Agno Database
    agno_db_url: str = "postgresql+psycopg://ai:ai@localhost:5532/ai"
    
    # Cognee Configuration
    require_auth: str = "true"
    allow_http_requests: str = "true"
    
    # JWT Configuration
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    
    # Admin User
    admin_username: str = "admin"
    admin_password: str = "change-this-password"
    
    # Environment
    environment: str = "development"  # development or production
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields
    )
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    @property
    def cookie_secure(self) -> bool:
        """Determine if cookies should be secure (HTTPS only)."""
        return self.is_production


# Global settings instance
settings = Settings()
