from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.core.database import get_db
from app.models.models import User, Account, Campaign, Group, Post, TaskLog
from app.models.schemas import (
    AccountCreate, AccountResponse, 
    CampaignCreate, CampaignResponse, CampaignUpdate,
    TaskLogResponse, PostResponse
)

router = APIRouter()

# --- Accounts ---
@router.post("/accounts/", response_model=AccountResponse)
async def create_account(account: AccountCreate, db: AsyncSession = Depends(get_db)):
    # Dla uproszczenia (MVP) przypisujemy do pierwszego użytkownika lub null
    db_account = Account(**account.dict())
    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    return db_account

@router.get("/accounts/", response_model=List[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account))
    return result.scalars().all()

# --- Campaigns ---
@router.post("/campaigns/", response_model=CampaignResponse)
async def create_campaign(campaign: CampaignCreate, db: AsyncSession = Depends(get_db)):
    # 1. Create Campaign
    db_campaign = Campaign(
        name=campaign.name,
        account_id=campaign.account_id,
        base_interval_minutes=campaign.base_interval_minutes,
        random_deviation_percent=campaign.random_deviation_percent,
        status="OCZEKUJE"
    )
    db.add(db_campaign)
    await db.flush() # Get campaign ID

    # 2. Add Groups
    for group_url in campaign.groups:
        db_group = Group(campaign_id=db_campaign.id, url=group_url)
        db.add(db_group)
    
    # 3. Add Posts
    for content in campaign.posts:
        db_post = Post(campaign_id=db_campaign.id, content=content)
        db.add(db_post)

    await db.commit()
    await db.refresh(db_campaign)
    return db_campaign

@router.get("/campaigns/", response_model=List[CampaignResponse])
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    return result.scalars().all()

@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign_status(campaign_id: int, update: CampaignUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    db_campaign = result.scalars().first()
    if not db_campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    db_campaign.status = update.status
    await db.commit()
    await db.refresh(db_campaign)
    return db_campaign

# --- Logs ---
@router.get("/logs/", response_model=List[TaskLogResponse])
async def list_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskLog).order_by(TaskLog.executed_at.desc()).limit(100))
    return result.scalars().all()

@router.get("/campaigns/{campaign_id}/posts", response_model=List[PostResponse])
async def get_campaign_posts(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).where(Post.campaign_id == campaign_id))
    return result.scalars().all()
