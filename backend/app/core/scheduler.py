import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import logging

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models import Campaign, Account, Group, TaskLog

logger = logging.getLogger(__name__)


async def check_active_campaigns():
    """
    Sprawdza aktywne kampanie i kolejkuje zadania publikacji.
    Publikuje grupy których planned_at <= now i nie mają SUCCESS loga.
    Uruchamiana cyklicznie przez Celery Beat lub APScheduler.
    """
    logger.info("Uruchamianie sprawdzania aktywnych kampanii...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.status == "AKTYWNA")
        )
        campaigns = result.scalars().all()

        now = datetime.now(timezone.utc)

        for campaign in campaigns:
            # Sprawdź start_at
            if campaign.start_at:
                start_at = campaign.start_at
                if start_at.tzinfo is None:
                    start_at = start_at.replace(tzinfo=timezone.utc)
                if now < start_at:
                    logger.info(f"Kampania {campaign.id} jeszcze nie wystartowała (start_at: {start_at})")
                    continue

            # Pobierz grupy z planned_at <= now, posortowane wg planned_at
            result_groups = await db.execute(
                select(Group).where(
                    Group.campaign_id == campaign.id,
                    Group.planned_at.isnot(None),
                    Group.planned_at <= now,
                ).order_by(Group.planned_at)
            )
            groups = result_groups.scalars().all()

            # Pobierz konto
            result_acc = await db.execute(
                select(Account).where(Account.id == campaign.account_id)
            )
            account = result_acc.scalars().first()

            if not account or not groups:
                continue

            for group in groups:
                # Sprawdź czy grupa już opublikowana pomyślnie
                result_log = await db.execute(
                    select(TaskLog).where(
                        TaskLog.group_id == group.id,
                        TaskLog.status == "SUCCESS"
                    )
                )
                if result_log.scalars().first():
                    continue

                # Sprawdź czy task jest już w toku
                in_flight_cutoff = now - timedelta(minutes=5)
                result_in_flight = await db.execute(
                    select(TaskLog).where(
                        TaskLog.group_id == group.id,
                        TaskLog.status.in_(["QUEUED", "EXCEPTION"]),
                        TaskLog.executed_at > in_flight_cutoff,
                    )
                )
                if result_in_flight.scalars().first():
                    logger.info(f"Grupa {group.id} ma task w toku, pomijam")
                    continue

                logger.info(f"Kolejkowanie postu do grupy: {group.url} (Kampania: {campaign.name})")

                queued_log = TaskLog(
                    group_id=group.id,
                    campaign_name=campaign.name,
                    status="QUEUED",
                )
                db.add(queued_log)
                await db.commit()

                if settings.STANDALONE:
                    from app.task_runner import submit_publish_task
                    await submit_publish_task(
                        profile_id=account.browser_profile_id,
                        account_email=account.fb_email,
                        account_pass=account.fb_password,
                        group_url=group.url,
                        post_content=group.content,
                        group_id=group.id,
                        campaign_name=campaign.name,
                        backup_cookies=account.session_cookies_backup,
                        background_style=group.background_style,
                    )
                else:
                    from app.worker import publish_post_task
                    publish_post_task.delay(
                        profile_id=account.browser_profile_id,
                        account_email=account.fb_email,
                        account_pass=account.fb_password,
                        group_url=group.url,
                        post_content=group.content,
                        group_id=group.id,
                        campaign_name=campaign.name,
                        backup_cookies=account.session_cookies_backup,
                        background_style=group.background_style,
                    )
                # 1 post per kampanię per cykl
                break

            # Sprawdź czy wszystkie grupy są gotowe
            all_groups_result = await db.execute(
                select(Group).where(Group.campaign_id == campaign.id)
            )
            all_groups = all_groups_result.scalars().all()
            all_done = True
            for g in all_groups:
                log_result = await db.execute(
                    select(TaskLog).where(TaskLog.group_id == g.id, TaskLog.status == "SUCCESS")
                )
                if not log_result.scalars().first():
                    all_done = False
                    break
            if all_done and all_groups:
                campaign.status = "ZAKOŃCZONA"
                await db.commit()
                logger.info(f"Kampania {campaign.id} zakończona — wszystkie grupy opublikowane")


def run_campaign_scheduler():
    """Synchroniczna funkcja wejścia dla Celery Beat."""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(check_active_campaigns())
