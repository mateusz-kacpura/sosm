from pydantic import BaseModel, EmailStr, HttpUrl
from typing import List, Optional
from datetime import datetime

# User Schemas
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# Account Schemas
class AccountBase(BaseModel):
    fb_email: str
    proxy_url: Optional[str] = None

class AccountCreate(AccountBase):
    fb_password: str

class AccountResponse(AccountBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Group Schemas
class GroupBase(BaseModel):
    url: str
    name: Optional[str] = None

class GroupResponse(GroupBase):
    id: int
    
    class Config:
        from_attributes = True

# Post Schemas
class PostBase(BaseModel):
    content: str
    media_urls: Optional[List[str]] = None

class PostResponse(PostBase):
    id: int

    class Config:
        from_attributes = True

# Campaign Schemas
class CampaignBase(BaseModel):
    name: str
    base_interval_minutes: int = 60
    random_deviation_percent: float = 10.0

class CampaignCreate(CampaignBase):
    account_id: int
    groups: List[str] # List of URLs
    posts: List[str]  # List of contents

class CampaignUpdate(BaseModel):
    status: str # OCZEKUJE, W TOKU, OPUBLIKOWANE, ZATRZYMANE

class CampaignResponse(CampaignBase):
    id: int
    status: str
    created_at: datetime
    account_id: int

    class Config:
        from_attributes = True

# Log Schemas
class TaskLogResponse(BaseModel):
    id: int
    post_id: int
    group_url: str
    status: str
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    executed_at: datetime

    class Config:
        from_attributes = True
