from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "sosm_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
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
import logging
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import Account, Group, TaskLog, FingerprintTest
from app.bot.browser_manager import BrowserManager
from app.bot.actions import FBActions
from app.bot.fingerprint_collector import collect_fingerprint, analyze_fingerprint

logger = logging.getLogger(__name__)

# Retry countdown wg dokumentacji: próba 2 → 5s, próba 3 → 10s, próba 4 → 20s
RETRY_COUNTDOWNS = [5, 10, 20]


async def run_bot_task(account_email: str, account_pass: str, proxy: str,
                       group_url: str, post_content: str, group_id: int,
                       campaign_name: str = ""):
    """Asynchroniczna funkcja wywoływana przez Celery w nowym event loopie."""
    async with AsyncSessionLocal() as db:
        try:
            async with BrowserManager(account_email, proxy) as manager:
                page = await manager.start()
                actions = FBActions(page, account_email)

                is_logged = await actions.login(account_pass)
                if not is_logged:
                    task_log = TaskLog(
                        group_id=group_id,
                        campaign_name=campaign_name,
                        status="CHECKPOINT_DETECTED",
                        error_message="Zablokowano na ekranie logowania",
                    )
                    db.add(task_log)
                    await db.commit()
                    return False

                success = await actions.publish_on_group(group_url, post_content)
                status = "SUCCESS" if success else "FAILED"
                error_msg = None if success else "Błąd publikacji / brak uprawnień na grupie"

                task_log = TaskLog(
                    group_id=group_id,
                    campaign_name=campaign_name,
                    status=status,
                    error_message=error_msg,
                )
                db.add(task_log)
                await db.commit()

                return success
        except Exception as e:
            task_log = TaskLog(
                group_id=group_id,
                campaign_name=campaign_name,
                status="EXCEPTION",
                error_message=str(e),
            )
            db.add(task_log)
            await db.commit()
            raise e


@celery_app.task(name="app.worker.check_campaigns_task")
def check_campaigns_task():
    """Wyzwalane przez Celery Beat co minutę."""
    from app.core.scheduler import run_campaign_scheduler
    run_campaign_scheduler()


@celery_app.task(
    name="app.worker.publish_post_task",
    bind=True,
    max_retries=3,
)
def publish_post_task(self, account_email: str, account_pass: str, proxy: str,
                      group_url: str, post_content: str, group_id: int,
                      campaign_name: str = ""):
    """Synchroniczna delegacja do asynchronicznego kodu Playwrighta."""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(
            run_bot_task(account_email, account_pass, proxy, group_url,
                         post_content, group_id, campaign_name)
        )
    except Exception as exc:
        retry_num = self.request.retries
        countdown = RETRY_COUNTDOWNS[retry_num] if retry_num < len(RETRY_COUNTDOWNS) else 20
        raise self.retry(exc=exc, countdown=countdown)


async def run_fingerprint_collection(test_id: int, proxy_url: str = None,
                                      visit_external_sites: bool = False):
    """Async: launch Camoufox, collect fingerprint, analyze, store results."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FingerprintTest).where(FingerprintTest.id == test_id)
        )
        fp_test = result.scalars().first()
        if not fp_test:
            return

        fp_test.status = "RUNNING"
        await db.commit()

        try:
            async with BrowserManager("fingerprint_test", proxy_url) as manager:
                page = await manager.start()

                raw_data = await collect_fingerprint(page)
                analysis = analyze_fingerprint(raw_data)

                results = {
                    "self_test": raw_data,
                    "analysis": analysis,
                    "external_sites": {},
                }

                if visit_external_sites:
                    external_sites = [
                        ("browserleaks", "https://browserleaks.com/canvas"),
                        ("pixelscan", "https://pixelscan.net/"),
                        ("creepjs", "https://abrahamjuliot.github.io/creepjs/"),
                    ]
                    for site_key, url in external_sites:
                        try:
                            await page.goto(url, wait_until="networkidle", timeout=30000)
                            await asyncio.sleep(5)
                            screenshot_path = f"/app/screenshots/fp_{test_id}_{site_key}.png"
                            await page.screenshot(path=screenshot_path, full_page=True)
                            results["external_sites"][site_key] = {
                                "url": url,
                                "screenshot_path": screenshot_path,
                                "visited": True,
                            }
                        except Exception as site_err:
                            results["external_sites"][site_key] = {
                                "url": url,
                                "visited": False,
                                "error": str(site_err),
                            }

            fp_test.results = results
            fp_test.status = "COMPLETED"
            fp_test.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            fp_test.status = "FAILED"
            fp_test.error_message = str(e)
            fp_test.completed_at = datetime.now(timezone.utc)
            await db.commit()
            raise e


@celery_app.task(name="app.worker.run_fingerprint_test_task")
def run_fingerprint_test_task(test_id: int, proxy_url: str = None,
                               visit_external_sites: bool = False):
    """Sync Celery entry point for fingerprint test."""
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(
        run_fingerprint_collection(test_id, proxy_url, visit_external_sites)
    )
