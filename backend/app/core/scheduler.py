import asyncio
import random
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
import logging

from app.core.database import AsyncSessionLocal
from app.models import Campaign, Account, Post, Group, TaskLog

logger = logging.getLogger(__name__)

async def check_active_campaigns():
    """
    Sprawdza aktywne kampanie w bazie danych i kolejkuje zadania do wykonania.
    Powinna być uruchamiana cyklicznie przez Celery Beat.
    """
    logger.info("Uruchamianie sprawdzania aktywnych kampanii...")
    async with AsyncSessionLocal() as db:
        # Pobieramy kampanie o statusie "W TOKU"
        result = await db.execute(
            select(Campaign).where(Campaign.status == "W TOKU")
        )
        campaigns = result.scalars().all()
        
        from app.worker import publish_post_task # Import opóźniony by uniknąć cyklicznych zależności
        
        for campaign in campaigns:
            # 1. Pobieramy posty do opublikowania dla tej kampanii
            result_posts = await db.execute(
                select(Post).where(Post.campaign_id == campaign.id)
            )
            posts = result_posts.scalars().all()
            
            # Pobieramy grupy dla kampanii
            result_groups = await db.execute(
                select(Group).where(Group.campaign_id == campaign.id)
            )
            groups = result_groups.scalars().all()
            
            # Pobieramy dane konta
            result_acc = await db.execute(
                select(Account).where(Account.id == campaign.account_id)
            )
            account = result_acc.scalars().first()
            
            if not account or not posts or not groups:
                continue
                
            # W pełnej logice sprawdzalibyśmy kiedy był ostatni Post w TaskLog. Wersja MVP: publikujemy pierwszy post gdzie TaskLog nie istnieje lub był FAIL
            for post in posts:
                for group in groups:
                    # Sprawdzamy czy post poszedł na daną grupkę
                    result_log = await db.execute(
                        select(TaskLog).where(
                            TaskLog.post_id == post.id,
                            TaskLog.group_url == group.url,
                            TaskLog.status == "SUCCESS"
                        ).order_by(TaskLog.executed_at.desc())
                    )
                    success_log = result_log.scalars().first()
                    
                    if not success_log:
                        # Post nie był jeszcze publikowany pomyślnie.
                        # Sprawdzamy kiedy ogólnie opublikowano JAKIKOLWIEK post dla TEJ kampanii
                        # żeby zachować odpowiedni interwał (base_interval_minutes + odchylenie)
                        result_last_log = await db.execute(
                            select(TaskLog)
                            .join(Post)
                            .where(Post.campaign_id == campaign.id, TaskLog.status == "SUCCESS")
                            .order_by(TaskLog.executed_at.desc())
                        )
                        last_log = result_last_log.scalars().first()
                        
                        should_publish = True
                        if last_log:
                            # Obliczanie losowego odchylenia do harmonogramu (np. z 60 min -> 54 - 66 min)
                            deviation_min = campaign.base_interval_minutes * (campaign.random_deviation_percent / 100.0)
                            random_deviation = random.uniform(-deviation_min, deviation_min)
                            target_interval = campaign.base_interval_minutes + random_deviation
                            
                            next_run_time = last_log.executed_at + timedelta(minutes=target_interval)
                            
                            # Upewniamy się, że czasy są "aware" do timezone
                            now = datetime.now(timezone.utc)
                            if last_log.executed_at.tzinfo is None:
                                last_log_aware = last_log.executed_at.replace(tzinfo=timezone.utc)
                                next_run_time = last_log_aware + timedelta(minutes=target_interval)
                                
                            if now < next_run_time:
                                should_publish = False
                                logger.info(f"Oczekiwanie na interwał dla kampanii {campaign.id}. Następny post o: {next_run_time}")
                                
                        if should_publish:
                            logger.info(f"Kolejkowanie postu do grupy: {group.url} (Kampania: {campaign.name})")
                            # Delegujemy na backend Celery
                            publish_post_task.delay(
                                account_email=account.fb_email,
                                account_pass=account.fb_password,
                                proxy=account.proxy_url,
                                group_url=group.url,
                                post_content=post.content,
                                post_id=post.id
                            )
                            # W jednym przebiegu limitujemy 1 post per kampanię by zachować odstęp.
                            break
                else:
                    continue # kontynuuj zewn. pętle
                break

def run_campaign_scheduler():
    """Funkcja wejścia synchroniczna np. dla Celery Beat lub Crona"""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    loop.run_until_complete(check_active_campaigns())
