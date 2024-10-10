from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import Request
from pydantic import BaseModel, EmailStr

from app.models.user import User


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    full_name: str
    password: str


class UserUpdate(UserBase):
    full_name: Optional[str]
    password: Optional[str]
    profile_picture: Optional[str]


class UserCreateResponse(UserBase):
    user_id: UUID
    full_name: str
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_user(cls, user: User, request: Request):
        profile_picture_url = str(request.base_url) + user.profile_picture.lstrip("/")
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            profile_picture=profile_picture_url,
        )


class CurrentUserResponse(BaseModel):
    email: str
    username: str
    full_name: str
    profile_picture: Optional[str]

    class Config:
        from_attributes = True