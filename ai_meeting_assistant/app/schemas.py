from pydantic import BaseModel, EmailStr
from typing import Optional


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class MeetingResponse(BaseModel):
    id: int
    title: str
    audio_path: str
    transcript: Optional[str] = None
    summary: Optional[str] = None
    action_items: Optional[str] = None
    status: str
    user_id: int

    class Config:
        from_attributes = True
