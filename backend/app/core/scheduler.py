import asyncio
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import logging

from app.core.database import AsyncSessionLocal
from app.models import Campaign, Account, Group, TaskLog

logger = logging.getLogger(__name__)


async def check_active_campaigns():
    """
    Sprawdza aktywne kampanie i kolejkuje zadania publikacji.
    Uruchamiana cyklicznie przez Celery Beat.
    """
    logger.info("Uruchamianie sprawdzania aktywnych kampanii...")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Campaign).where(Campaign.status == "AKTYWNA")
        )
        campaigns = result.scalars().all()

        from app.worker import publish_post_task

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

            # Pobierz grupy (posortowane wg order)
            result_groups = await db.execute(
                select(Group).where(Group.campaign_id == campaign.id).order_by(Group.order)
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
                    ).order_by(TaskLog.executed_at.desc())
                )
                success_log = result_log.scalars().first()

                if not success_log:
                    # Sprawdź interwał od ostatniego SUCCESS w tej kampanii
                    result_last_log = await db.execute(
                        select(TaskLog)
                        .join(Group)
                        .where(Group.campaign_id == campaign.id, TaskLog.status == "SUCCESS")
                        .order_by(TaskLog.executed_at.desc())
                    )
                    last_log = result_last_log.scalars().first()

                    should_publish = True
                    if last_log:
                        deviation_min = campaign.base_interval_minutes * (campaign.random_deviation_percent / 100.0)
                        random_deviation = random.uniform(-deviation_min, deviation_min)
                        target_interval = campaign.base_interval_minutes + random_deviation

                        last_executed = last_log.executed_at
                        if last_executed.tzinfo is None:
                            last_executed = last_executed.replace(tzinfo=timezone.utc)

                        next_run_time = last_executed + timedelta(minutes=target_interval)

                        if now < next_run_time:
                            should_publish = False
                            logger.info(f"Oczekiwanie na interwał dla kampanii {campaign.id}. Następny post o: {next_run_time}")

                    if should_publish:
                        logger.info(f"Kolejkowanie postu do grupy: {group.url} (Kampania: {campaign.name})")
                        publish_post_task.delay(
                            account_email=account.fb_email,
                            account_pass=account.fb_password,
                            proxy=account.proxy_url,
                            group_url=group.url,
                            post_content=group.content,
                            group_id=group.id,
                            campaign_name=campaign.name,
                        )
                        # Limit: 1 post per kampanię per cykl
                        break


def run_campaign_scheduler():
    """Synchroniczna funkcja wejścia dla Celery Beat."""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(check_active_campaigns())
