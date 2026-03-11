from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "sosm_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],  # Ignore other content
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    broker_connection_retry_on_startup=True
)

celery_app.conf.beat_schedule = {
    'check-active-campaigns-every-minute': {
        'task': 'app.worker.check_campaigns_task',
        'schedule': 60.0,
    },
}

import asyncio
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import Account, Post, Group, TaskLog
from app.bot.browser_manager import BrowserManager
from app.bot.actions import FBActions

async def run_bot_task(account_email: str, account_pass: str, proxy: str, group_url: str, post_content: str, post_id: int):
    """Asynchroniczna funkcja wywoływana przez Celery w nowym event loopie"""
    async with AsyncSessionLocal() as db:
        try:
            async with BrowserManager(account_email, proxy) as manager:
                page = await manager.start()
                actions = FBActions(page, account_email)
                
                # 1. Logowanie
                is_logged = await actions.login(account_pass)
                if not is_logged:
                    # Logujemy faliure do bazy
                    task_log = TaskLog(post_id=post_id, group_url=group_url, status="CHECKPOINT_DETECTED", error_message="Zablokowano na ekranie logowania")
                    db.add(task_log)
                    await db.commit()
                    return False
                
                # 2. Publikowanie na grupie
                success = await actions.publish_on_group(group_url, post_content)
                status = "SUCCESS" if success else "FAILED"
                error_msg = None if success else "Błąd publikacji / brak uprawnień na grupie"
                
                # 3. Zapis do bilingów zadań
                task_log = TaskLog(post_id=post_id, group_url=group_url, status=status, error_message=error_msg)
                db.add(task_log)
                await db.commit()
                
                return success
        except Exception as e:
            task_log = TaskLog(post_id=post_id, group_url=group_url, status="EXCEPTION", error_message=str(e))
            db.add(task_log)
            await db.commit()
            raise e

@celery_app.task(name="app.worker.check_campaigns_task")
def check_campaigns_task():
    """Wyzwalane przez Celery Beat co minutę"""
    from app.core.scheduler import run_campaign_scheduler
    run_campaign_scheduler()

@celery_app.task(
    name="app.worker.publish_post_task", 
    bind=True, 
    autoretry_for=(Exception,), 
    retry_kwargs={'max_retries': 3, 'countdown': 300} # ponów max 3 razy, co 5 minut w przypadku błędu
)
def publish_post_task(self, account_email: str, account_pass: str, proxy: str, group_url: str, post_content: str, post_id: int):
    """
    Synchroniczna delegacja wywoływana przez API do wykonania asynchronicznego kodu Playwrighta.
    Tworzy oddzielny event_loop by obejść ograniczenia Celery workerów z asyncio.
    """
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        return loop.run_until_complete(
            run_bot_task(account_email, account_pass, proxy, group_url, post_content, post_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)

