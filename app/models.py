"""SQLAlchemy models for the application."""
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """User model with JWT scope-based access control."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    scopes = Column(JSON, nullable=False)  # Array of scopes: ['admin'] or ['user']
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<User(id={self.id}, username={self.username}, scopes={self.scopes}, is_active={self.is_active})>"


class Role(Base):
    """Role model (optional - can use scopes directly)."""
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)  # 'Admin' or 'End_User'
    scope = Column(String, nullable=False)  # Maps to JWT scope: 'admin' or 'user'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name}, scope={self.scope})>"
