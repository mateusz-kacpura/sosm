from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


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
class GroupInput(BaseModel):
    url: str
    content: str
    media_urls: Optional[List[str]] = None

class GroupResponse(BaseModel):
    id: int
    url: str
    name: Optional[str] = None
    content: str
    media_urls: Optional[List[str]] = None
    order: int

    class Config:
        from_attributes = True


# Campaign Schemas
class CampaignBase(BaseModel):
    name: str
    base_interval_minutes: int = 60
    random_deviation_percent: float = 10.0

class CampaignCreate(CampaignBase):
    account_id: int
    groups: List[GroupInput]
    start_at: Optional[datetime] = None

class CampaignUpdate(BaseModel):
    status: str  # SZKIC, AKTYWNA, WSTRZYMANA, ZAKOŃCZONA, BŁĄD

class CampaignResponse(CampaignBase):
    id: int
    status: str
    start_at: Optional[datetime] = None
    created_at: datetime
    account_id: int

    class Config:
        from_attributes = True


# Log Schemas
class TaskLogResponse(BaseModel):
    id: int
    group_id: int
    campaign_name: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    planned_at: Optional[datetime] = None
    retry_count: int = 0
    executed_at: datetime

    class Config:
        from_attributes = True


# Fingerprint Test Schemas
class FingerprintTestCreate(BaseModel):
    account_id: Optional[int] = None
    visit_external_sites: bool = False

class FingerprintTestResponse(BaseModel):
    id: int
    account_id: Optional[int] = None
    status: str
    proxy_url_used: Optional[str] = None
    results: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class FingerprintTestSummary(BaseModel):
    id: int
    account_id: Optional[int] = None
    status: str
    proxy_url_used: Optional[str] = None
    overall_score: Optional[int] = None
    overall_status: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
