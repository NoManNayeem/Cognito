"""Pydantic schemas for request/response validation."""
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema."""
    username: str


class UserCreate(UserBase):
    """Schema for user creation."""
    password: str


class UserResponse(UserBase):
    """Schema for user response."""
    id: int
    is_active: bool
    scopes: List[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    """Schema for user login."""
    username: str
    password: str


class Token(BaseModel):
    """Schema for JWT token."""
    access_token: str
    token_type: str = "bearer"
    scopes: List[str]


class ChatMessage(BaseModel):
    """Schema for chat message."""
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Schema for chat response."""
    response: str
    session_id: str


class StatsResponse(BaseModel):
    """Schema for admin statistics."""
    total_users: int
    total_conversations: int
    total_files: int
    total_urls: int
