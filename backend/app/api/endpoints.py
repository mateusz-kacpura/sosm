from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from typing import List
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.models import Account, Campaign, Group, TaskLog, FingerprintTest
from app.models.schemas import (
    AccountCreate, AccountResponse,
    CampaignCreate, CampaignResponse, CampaignUpdate,
    TaskLogResponse, GroupResponse,
    FingerprintTestCreate, FingerprintTestResponse, FingerprintTestSummary,
)

router = APIRouter()


# --- Accounts ---
@router.post("/accounts/", response_model=AccountResponse)
async def create_account(account: AccountCreate, db: AsyncSession = Depends(get_db)):
    db_account = Account(**account.model_dump())
    db.add(db_account)
    await db.commit()
    await db.refresh(db_account)
    return db_account

@router.get("/accounts/", response_model=List[AccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account))
    return result.scalars().all()

@router.delete("/accounts/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Account).where(Account.id == account_id))
    db_account = result.scalars().first()
    if not db_account:
        raise HTTPException(status_code=404, detail="Account not found")
    await db.delete(db_account)
    await db.commit()
    return {"detail": "Account deleted"}


# --- Campaigns ---
@router.post("/campaigns/", response_model=CampaignResponse)
async def create_campaign(campaign: CampaignCreate, db: AsyncSession = Depends(get_db)):
    db_campaign = Campaign(
        name=campaign.name,
        account_id=campaign.account_id,
        base_interval_minutes=campaign.base_interval_minutes,
        random_deviation_percent=campaign.random_deviation_percent,
        status="SZKIC",
        start_at=campaign.start_at,
    )
    db.add(db_campaign)
    await db.flush()

    for i, group_input in enumerate(campaign.groups):
        db_group = Group(
            campaign_id=db_campaign.id,
            url=group_input.url,
            content=group_input.content,
            media_urls=group_input.media_urls,
            order=i,
        )
        db.add(db_group)

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

@router.get("/campaigns/{campaign_id}/groups", response_model=List[GroupResponse])
async def get_campaign_groups(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Group).where(Group.campaign_id == campaign_id).order_by(Group.order)
    )
    return result.scalars().all()


# --- Logs ---
@router.get("/logs/", response_model=List[TaskLogResponse])
async def list_logs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(TaskLog).order_by(TaskLog.executed_at.desc()).limit(100))
    return result.scalars().all()


# --- Stats ---
@router.get("/stats/")
async def get_stats(db: AsyncSession = Depends(get_db)):
    active_result = await db.execute(
        select(sa_func.count()).select_from(Campaign).where(Campaign.status == "AKTYWNA")
    )
    active_campaigns = active_result.scalar() or 0

    accounts_result = await db.execute(
        select(sa_func.count()).select_from(Account)
    )
    total_accounts = accounts_result.scalar() or 0

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    posts_today_result = await db.execute(
        select(sa_func.count()).select_from(TaskLog).where(
            TaskLog.status == "SUCCESS",
            TaskLog.executed_at >= today_start,
        )
    )
    posts_today = posts_today_result.scalar() or 0

    total_logs_result = await db.execute(
        select(sa_func.count()).select_from(TaskLog)
    )
    total_logs = total_logs_result.scalar() or 0

    success_logs_result = await db.execute(
        select(sa_func.count()).select_from(TaskLog).where(TaskLog.status == "SUCCESS")
    )
    success_logs = success_logs_result.scalar() or 0

    success_rate = f"{round(success_logs / total_logs * 100)}%" if total_logs > 0 else "0%"

    return {
        "active_campaigns": active_campaigns,
        "total_accounts": total_accounts,
        "posts_today": posts_today,
        "success_rate": success_rate,
    }


# --- Fingerprint Tests ---
@router.post("/fingerprint-tests/", response_model=FingerprintTestResponse)
async def create_fingerprint_test(request: FingerprintTestCreate, db: AsyncSession = Depends(get_db)):
    proxy_url = None
    if request.account_id:
        result = await db.execute(select(Account).where(Account.id == request.account_id))
        account = result.scalars().first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        proxy_url = account.proxy_url

    db_test = FingerprintTest(
        account_id=request.account_id,
        status="PENDING",
        proxy_url_used=proxy_url,
    )
    db.add(db_test)
    await db.commit()
    await db.refresh(db_test)

    from app.worker import run_fingerprint_test_task
    run_fingerprint_test_task.delay(
        test_id=db_test.id,
        proxy_url=proxy_url,
        visit_external_sites=request.visit_external_sites,
    )

    db_test.status = "RUNNING"
    await db.commit()
    await db.refresh(db_test)
    return db_test

@router.get("/fingerprint-tests/", response_model=List[FingerprintTestSummary])
async def list_fingerprint_tests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FingerprintTest).order_by(FingerprintTest.created_at.desc()).limit(50)
    )
    tests = result.scalars().all()
    summaries = []
    for t in tests:
        overall_score = None
        overall_status = None
        if t.results and "analysis" in t.results:
            overall_score = t.results["analysis"].get("overall_score")
            overall_status = t.results["analysis"].get("overall_status")
        summaries.append(FingerprintTestSummary(
            id=t.id,
            account_id=t.account_id,
            status=t.status,
            proxy_url_used=t.proxy_url_used,
            overall_score=overall_score,
            overall_status=overall_status,
            error_message=t.error_message,
            created_at=t.created_at,
            completed_at=t.completed_at,
        ))
    return summaries

@router.get("/fingerprint-tests/{test_id}", response_model=FingerprintTestResponse)
async def get_fingerprint_test(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FingerprintTest).where(FingerprintTest.id == test_id))
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Fingerprint test not found")
    return test

@router.delete("/fingerprint-tests/{test_id}")
async def delete_fingerprint_test(test_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FingerprintTest).where(FingerprintTest.id == test_id))
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Fingerprint test not found")
    await db.delete(test)
    await db.commit()
    return {"detail": "Fingerprint test deleted"}
