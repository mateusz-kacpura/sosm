import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func as sa_func
from typing import List
from datetime import datetime, timezone, timedelta

from app.core.database import get_db
from app.models.models import Account, Campaign, Group, TaskLog, FingerprintTest
from app.models.schemas import (
    AccountCreate, AccountResponse,
    CampaignCreate, CampaignResponse, CampaignUpdate,
    TaskLogResponse, GroupResponse, GroupUpdate, CampaignGroupsReplace,
    FingerprintTestCreate, FingerprintTestResponse, FingerprintTestSummary,
)

router = APIRouter()


# --- Accounts ---
def _donut_client():
    from app.core.config import settings
    from app.bot.donut_client import DonutClient
    return DonutClient(settings.DONUT_API_URL, settings.DONUT_API_TOKEN)


@router.post("/accounts/", response_model=AccountResponse)
async def create_account(account: AccountCreate, db: AsyncSession = Depends(get_db)):
    data = account.model_dump()

    # Auto-create Donut Browser profile if not provided
    if not data.get("browser_profile_id"):
        try:
            client = _donut_client()
            profile_id = await client.create_profile(name=data["fb_email"])
            data["browser_profile_id"] = profile_id
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"Nie udalo sie utworzyc profilu przegladarki: {e}"
            )

    db_account = Account(**data)
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

    # Delete Donut Browser profile if exists
    if db_account.browser_profile_id:
        try:
            client = _donut_client()
            await client.delete_profile(db_account.browser_profile_id)
        except Exception:
            pass  # Profile cleanup is best-effort

    await db.delete(db_account)
    await db.commit()
    return {"detail": "Account deleted"}


def _compute_interval(posts_per_day: int, hours_start: str, hours_end: str) -> int:
    """Compute base_interval_minutes from posts_per_day and active window."""
    sh, sm = int(hours_start[:2]), int(hours_start[3:5])
    eh, em = int(hours_end[:2]), int(hours_end[3:5])
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    if end_min <= start_min:
        end_min += 24 * 60  # overnight window
    window = end_min - start_min
    ppd = max(1, posts_per_day)
    return max(30, window // ppd)


# --- Campaigns ---
@router.post("/campaigns/", response_model=CampaignResponse)
async def create_campaign(campaign: CampaignCreate, db: AsyncSession = Depends(get_db)):
    hours_start = campaign.active_hours_start or "08:00"
    hours_end = campaign.active_hours_end or "22:00"
    interval = _compute_interval(campaign.posts_per_day, hours_start, hours_end)

    db_campaign = Campaign(
        name=campaign.name,
        account_id=campaign.account_id,
        posts_per_day=campaign.posts_per_day,
        base_interval_minutes=interval,
        active_hours_start=hours_start,
        active_hours_end=hours_end,
        active_days=campaign.active_days,
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
            background_style=group_input.background_style,
            planned_at=group_input.planned_at,
            order=i,
        )
        db.add(db_group)

    await db.commit()
    await db.refresh(db_campaign)
    return db_campaign

@router.get("/campaigns/")
async def list_campaigns(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = result.scalars().all()

    response = []
    for camp in campaigns:
        count_result = await db.execute(
            select(sa_func.count()).select_from(Group).where(Group.campaign_id == camp.id)
        )
        groups_count = count_result.scalar() or 0
        data = CampaignResponse.model_validate(camp).model_dump()
        data["groups_count"] = groups_count
        response.append(data)
    return response

@router.patch("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: int, update: CampaignUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    db_campaign = result.scalars().first()
    if not db_campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(db_campaign, field, value)

    # Recompute interval if schedule params changed
    changed = update.model_fields_set
    if changed & {"posts_per_day", "active_hours_start", "active_hours_end"}:
        db_campaign.base_interval_minutes = _compute_interval(
            db_campaign.posts_per_day or 1,
            db_campaign.active_hours_start or "08:00",
            db_campaign.active_hours_end or "22:00",
        )

    await db.commit()
    await db.refresh(db_campaign)
    return db_campaign

@router.put("/campaigns/{campaign_id}/groups", response_model=List[GroupResponse])
async def replace_campaign_groups(
    campaign_id: int, payload: CampaignGroupsReplace, db: AsyncSession = Depends(get_db)
):
    """Replace all groups in a campaign (delete existing, create new)."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Delete existing groups and their task logs
    existing = await db.execute(select(Group).where(Group.campaign_id == campaign_id))
    existing_groups = existing.scalars().all()
    if existing_groups:
        from sqlalchemy import delete as sa_delete
        existing_ids = [g.id for g in existing_groups]
        await db.execute(
            sa_delete(TaskLog).where(TaskLog.group_id.in_(existing_ids))
        )
        for g in existing_groups:
            await db.delete(g)
    await db.flush()

    # Revert campaign from ZAKOŃCZONA so new groups can be scheduled
    if campaign.status == "ZAKOŃCZONA":
        campaign.status = "AKTYWNA"

    # Create new groups
    new_groups = []
    for i, group_input in enumerate(payload.groups):
        db_group = Group(
            campaign_id=campaign_id,
            url=group_input.url,
            content=group_input.content,
            media_urls=group_input.media_urls,
            background_style=group_input.background_style,
            planned_at=group_input.planned_at,
            order=i,
        )
        db.add(db_group)
        new_groups.append(db_group)

    await db.commit()
    for g in new_groups:
        await db.refresh(g)
    return new_groups


@router.get("/campaigns/{campaign_id}/groups", response_model=List[GroupResponse])
async def get_campaign_groups(campaign_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Group).where(Group.campaign_id == campaign_id).order_by(Group.order)
    )
    return result.scalars().all()


@router.post("/campaigns/{campaign_id}/generate-schedule")
async def generate_schedule(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Auto-generate planned_at dates for all unposted groups in a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result_groups = await db.execute(
        select(Group).where(Group.campaign_id == campaign_id).order_by(Group.order)
    )
    groups = result_groups.scalars().all()

    now = datetime.now(timezone.utc)
    active_days = campaign.active_days if campaign.active_days is not None else [0, 1, 2, 3, 4, 5, 6]
    start_h = campaign.active_hours_start or "08:00"
    end_h = campaign.active_hours_end or "22:00"
    ppd = max(1, campaign.posts_per_day or 1)

    sh, sm = int(start_h[:2]), int(start_h[3:5])
    eh, em = int(end_h[:2]), int(end_h[3:5])

    # Window size in minutes
    start_min = sh * 60 + sm
    end_min = eh * 60 + em
    if end_min <= start_min:
        end_min += 24 * 60
    window_min = end_min - start_min

    # Start cursor
    if campaign.start_at:
        start_at = campaign.start_at
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)
        cursor_day = max(start_at, now).date()
    else:
        cursor_day = now.date()

    slots_used_today = 0
    updated = 0

    for group in groups:
        # Skip already posted (check SUCCESS log)
        result_log = await db.execute(
            select(TaskLog).where(TaskLog.group_id == group.id, TaskLog.status == "SUCCESS")
        )
        if result_log.scalars().first():
            continue

        # Find next valid slot
        for _ in range(365):
            weekday = cursor_day.weekday()
            if weekday in active_days:
                if slots_used_today < ppd:
                    # Pick a random time within the window slice for this slot
                    slot_size = window_min // ppd
                    slot_start = start_min + slots_used_today * slot_size
                    slot_end = slot_start + slot_size
                    rand_min = random.randint(slot_start + 5, max(slot_start + 6, slot_end - 5))
                    planned = datetime(
                        cursor_day.year, cursor_day.month, cursor_day.day,
                        rand_min // 60 % 24, rand_min % 60,
                        tzinfo=timezone.utc,
                    )
                    # Don't schedule in the past
                    if planned <= now:
                        slots_used_today += 1
                        if slots_used_today >= ppd:
                            cursor_day += timedelta(days=1)
                            slots_used_today = 0
                        continue

                    group.planned_at = planned
                    updated += 1
                    slots_used_today += 1
                    if slots_used_today >= ppd:
                        cursor_day += timedelta(days=1)
                        slots_used_today = 0
                    break
                else:
                    cursor_day += timedelta(days=1)
                    slots_used_today = 0
            else:
                cursor_day += timedelta(days=1)
                slots_used_today = 0

    await db.commit()
    return {"updated": updated, "total_groups": len(groups)}


@router.patch("/groups/{group_id}", response_model=GroupResponse)
async def update_group(group_id: int, update: GroupUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalars().first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    update_data = update.model_dump(exclude_unset=True)
    reschedule = "planned_at" in update_data

    for field, value in update_data.items():
        setattr(group, field, value)

    if reschedule:
        # Clear old task logs so the group can be re-published
        from sqlalchemy import delete as sa_delete
        await db.execute(
            sa_delete(TaskLog).where(TaskLog.group_id == group_id)
        )
        # Revert campaign from ZAKOŃCZONA if needed
        campaign_result = await db.execute(
            select(Campaign).where(Campaign.id == group.campaign_id)
        )
        campaign = campaign_result.scalars().first()
        if campaign and campaign.status == "ZAKOŃCZONA":
            campaign.status = "AKTYWNA"

    await db.commit()
    await db.refresh(group)
    return group


def _advance_to_schedule(candidate: datetime, campaign) -> datetime:
    """Advance a candidate datetime to the next valid schedule slot."""
    active_days = campaign.active_days if campaign.active_days is not None else [0, 1, 2, 3, 4, 5, 6]
    start_h = campaign.active_hours_start or "08:00"
    end_h = campaign.active_hours_end or "22:00"

    sh, sm = int(start_h[:2]), int(start_h[3:5])

    for _ in range(14):  # max 2 weeks lookahead
        if candidate.weekday() in active_days:
            ct = candidate.strftime("%H:%M")
            if start_h <= end_h:
                if ct < start_h:
                    candidate = candidate.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    return candidate
                elif ct <= end_h:
                    return candidate
            else:
                if ct >= start_h or ct <= end_h:
                    return candidate
        # Move to start of next day
        candidate = (candidate + timedelta(days=1)).replace(
            hour=sh, minute=sm, second=0, microsecond=0
        )

    return candidate


@router.get("/campaigns/{campaign_id}/schedule-preview")
async def get_schedule_preview(campaign_id: int, db: AsyncSession = Depends(get_db)):
    """Preview estimated post schedule for a campaign."""
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalars().first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    result_groups = await db.execute(
        select(Group).where(Group.campaign_id == campaign_id).order_by(Group.order)
    )
    groups = result_groups.scalars().all()

    now = datetime.now(timezone.utc)
    schedule = []
    prev_estimated = None

    for group in groups:
        # Check for existing logs
        result_success = await db.execute(
            select(TaskLog).where(
                TaskLog.group_id == group.id,
                TaskLog.status == "SUCCESS",
            ).order_by(TaskLog.executed_at.desc())
        )
        success_log = result_success.scalars().first()

        result_queued = await db.execute(
            select(TaskLog).where(
                TaskLog.group_id == group.id,
                TaskLog.status == "QUEUED",
            ).order_by(TaskLog.executed_at.desc())
        )
        queued_log = result_queued.scalars().first()

        result_failed = await db.execute(
            select(TaskLog).where(
                TaskLog.group_id == group.id,
                TaskLog.status.in_(["FAILED", "CHECKPOINT_DETECTED"]),
            ).order_by(TaskLog.executed_at.desc())
        )
        failed_log = result_failed.scalars().first()

        if success_log:
            schedule.append({
                "group_id": group.id,
                "group_url": group.url,
                "content_preview": group.content[:80],
                "estimated_at": success_log.executed_at.isoformat(),
                "status": "completed",
            })
            prev_estimated = success_log.executed_at
        elif queued_log:
            schedule.append({
                "group_id": group.id,
                "group_url": group.url,
                "content_preview": group.content[:80],
                "estimated_at": queued_log.executed_at.isoformat(),
                "status": "queued",
            })
            prev_estimated = queued_log.executed_at
        else:
            # Estimate future post time
            if prev_estimated:
                candidate = prev_estimated + timedelta(minutes=campaign.base_interval_minutes)
            elif campaign.start_at:
                start_at = campaign.start_at
                if start_at.tzinfo is None:
                    start_at = start_at.replace(tzinfo=timezone.utc)
                candidate = max(start_at, now)
            else:
                candidate = now

            candidate = _advance_to_schedule(candidate, campaign)
            status = "failed_retry" if failed_log else "scheduled"

            schedule.append({
                "group_id": group.id,
                "group_url": group.url,
                "content_preview": group.content[:80],
                "estimated_at": candidate.isoformat(),
                "status": status,
            })
            prev_estimated = candidate

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
        "active_hours": f"{campaign.active_hours_start or '08:00'}-{campaign.active_hours_end or '22:00'}",
        "active_days": campaign.active_days or [0, 1, 2, 3, 4, 5, 6],
        "posts_per_day": campaign.posts_per_day or 1,
        "schedule": schedule,
    }


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

    # Use account's browser profile if available, otherwise the default fingerprint profile
    fp_profile_id = None
    if request.account_id:
        result2 = await db.execute(select(Account).where(Account.id == request.account_id))
        acc = result2.scalars().first()
        if acc:
            fp_profile_id = acc.browser_profile_id

    from app.core.config import settings as _settings
    if _settings.STANDALONE:
        from app.task_runner import submit_fingerprint_task
        await submit_fingerprint_task(
            test_id=db_test.id,
            profile_id=fp_profile_id,
            visit_external_sites=request.visit_external_sites,
        )
    else:
        from app.worker import run_fingerprint_test_task
        run_fingerprint_test_task.delay(
            test_id=db_test.id,
            profile_id=fp_profile_id,
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
