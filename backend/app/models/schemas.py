from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


# Account Schemas
class AccountBase(BaseModel):
    fb_email: str
    proxy_url: Optional[str] = None
    browser_profile_id: Optional[str] = None

class AccountCreate(BaseModel):
    fb_email: str
    fb_password: str
    proxy_url: Optional[str] = None

class FanpageCreate(BaseModel):
    fanpage_url: str
    fanpage_name: Optional[str] = None

class FanpageResponse(BaseModel):
    id: int
    account_id: int
    fanpage_url: str
    fanpage_name: Optional[str] = None
    created_at: datetime
    verification_status: str = "UNVERIFIED"
    verification_error: Optional[str] = None
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AccountResponse(AccountBase):
    id: int
    created_at: datetime
    fanpages: list[FanpageResponse] = []
    fanpage_discovery_status: Optional[str] = None
    fanpage_discovery_error: Optional[str] = None

    class Config:
        from_attributes = True


# Group Schemas
class GroupInput(BaseModel):
    url: str
    content: str
    media_urls: Optional[List[str]] = None
    background_style: Optional[str] = None
    planned_at: Optional[datetime] = None

class GroupResponse(BaseModel):
    id: int
    url: str
    name: Optional[str] = None
    content: str
    media_urls: Optional[List[str]] = None
    background_style: Optional[str] = None
    order: int
    planned_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class GroupUpdate(BaseModel):
    planned_at: Optional[datetime] = None
    content: Optional[str] = None
    url: Optional[str] = None
    background_style: Optional[str] = None

class CampaignGroupsReplace(BaseModel):
    groups: List[GroupInput]


# Campaign Schemas
class CampaignBase(BaseModel):
    name: str
    posts_per_day: int = 1
    active_hours_start: Optional[str] = "08:00"
    active_hours_end: Optional[str] = "22:00"
    active_days: Optional[list[int]] = [0, 1, 2, 3, 4, 5, 6]

class CampaignCreate(CampaignBase):
    account_id: int
    groups: List[GroupInput]
    start_at: Optional[datetime] = None

class CampaignUpdate(BaseModel):
    status: Optional[str] = None  # SZKIC, AKTYWNA, WSTRZYMANA, ZAKOŃCZONA, BŁĄD
    name: Optional[str] = None
    posts_per_day: Optional[int] = None
    active_hours_start: Optional[str] = None
    active_hours_end: Optional[str] = None
    active_days: Optional[list[int]] = None
    start_at: Optional[datetime] = None

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
    group_id: Optional[int] = None
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
