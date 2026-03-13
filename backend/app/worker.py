from app.core.config import settings

# Celery + Redis only in Docker mode
if not settings.STANDALONE:
    from celery import Celery
    import redis

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

    _redis_client = redis.Redis.from_url(settings.REDIS_URL)
    _PROFILE_LOCK_TTL = 300

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

RETRY_COUNTDOWNS = [5, 10, 20]


async def _clear_queued_logs(db, group_id: int):
    """Remove QUEUED markers for a group now that the task has a final status."""
    from sqlalchemy import delete as sa_delete
    await db.execute(
        sa_delete(TaskLog).where(
            TaskLog.group_id == group_id,
            TaskLog.status == "QUEUED",
        )
    )


async def run_bot_task(profile_id: str, account_email: str, account_pass: str,
                       group_url: str, post_content: str, group_id: int,
                       campaign_name: str = "",
                       backup_cookies: dict = None,
                       background_style: str = None):
    """Async function: connects to Donut Browser profile via nodriver (CDP),
    performs login + publish. Used by both Celery and standalone task runner."""
    async with AsyncSessionLocal() as db:
        try:
            manager = BrowserManager(profile_id)
            tab = await manager.start(backup_cookies=backup_cookies)

            try:
                actions = FBActions(tab, account_email)

                is_logged = await actions.login(account_pass)
                if not is_logged:
                    await _clear_queued_logs(db, group_id)
                    task_log = TaskLog(
                        group_id=group_id,
                        campaign_name=campaign_name,
                        status="CHECKPOINT_DETECTED",
                        error_message="Zablokowano na ekranie logowania",
                    )
                    db.add(task_log)
                    await db.commit()
                    return False

                success = await actions.publish_on_group(group_url, post_content, background_style=background_style)
                status = "SUCCESS" if success else "FAILED"
                error_msg = None if success else "Blad publikacji / brak uprawnien na grupie"

                cookies = await manager.extract_session_cookies(tab)
                if cookies:
                    result = await db.execute(
                        select(Account).where(Account.browser_profile_id == profile_id)
                    )
                    account = result.scalars().first()
                    if account:
                        account.session_cookies_backup = cookies

                await _clear_queued_logs(db, group_id)
                task_log = TaskLog(
                    group_id=group_id,
                    campaign_name=campaign_name,
                    status=status,
                    error_message=error_msg,
                )
                db.add(task_log)
                await db.commit()

                return success
            finally:
                await manager.stop()

        except Exception as e:
            await _clear_queued_logs(db, group_id)
            task_log = TaskLog(
                group_id=group_id,
                campaign_name=campaign_name,
                status="EXCEPTION",
                error_message=str(e),
            )
            db.add(task_log)
            await db.commit()
            raise e


async def run_fingerprint_collection(test_id: int, profile_id: str = None,
                                      visit_external_sites: bool = False):
    """Async: connect to Donut Browser profile, collect fingerprint, analyze, store results."""
    import os
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FingerprintTest).where(FingerprintTest.id == test_id)
        )
        fp_test = result.scalars().first()
        if not fp_test:
            return

        fp_test.status = "RUNNING"
        await db.commit()

        fp_profile_id = profile_id or settings.FINGERPRINT_PROFILE_ID

        try:
            manager = BrowserManager(fp_profile_id)
            tab = await manager.start()

            try:
                raw_data = await collect_fingerprint(tab)
                analysis = analyze_fingerprint(raw_data)

                results = {
                    "self_test": raw_data,
                    "analysis": analysis,
                    "external_sites": {},
                }

                if visit_external_sites:
                    screenshot_dir = os.path.join(settings.DATA_DIR, "screenshots")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    external_sites = [
                        ("browserleaks", "https://browserleaks.com/canvas"),
                        ("pixelscan", "https://pixelscan.net/"),
                        ("creepjs", "https://abrahamjuliot.github.io/creepjs/"),
                    ]
                    for site_key, url in external_sites:
                        try:
                            await tab.get(url)
                            await asyncio.sleep(8)
                            screenshot_path = os.path.join(screenshot_dir, f"fp_{test_id}_{site_key}.png")
                            await tab.save_screenshot(screenshot_path)
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
            finally:
                await manager.stop()

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


# Celery task wrappers (Docker mode only)
if not settings.STANDALONE:
    @celery_app.task(name="app.worker.check_campaigns_task")
    def check_campaigns_task():
        """Triggered by Celery Beat every minute."""
        from app.core.scheduler import run_campaign_scheduler
        run_campaign_scheduler()

    @celery_app.task(
        name="app.worker.publish_post_task",
        bind=True,
        max_retries=3,
    )
    def publish_post_task(self, profile_id: str, account_email: str, account_pass: str,
                          group_url: str, post_content: str, group_id: int,
                          campaign_name: str = "",
                          backup_cookies: dict = None,
                          background_style: str = None):
        """Sync Celery entry point — delegates to async nodriver code."""
        lock_key = f"sosm:profile_lock:{profile_id}"
        lock = _redis_client.lock(lock_key, timeout=_PROFILE_LOCK_TTL, blocking_timeout=120)
        if not lock.acquire(blocking=True):
            logger.warning("Profile %s still locked after 120s, skipping", profile_id)
            return None

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(
                run_bot_task(profile_id, account_email, account_pass,
                             group_url, post_content, group_id, campaign_name,
                             backup_cookies, background_style)
            )
        except Exception as exc:
            retry_num = self.request.retries
            countdown = RETRY_COUNTDOWNS[retry_num] if retry_num < len(RETRY_COUNTDOWNS) else 20
            raise self.retry(exc=exc, countdown=countdown)
        finally:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    @celery_app.task(name="app.worker.run_fingerprint_test_task")
    def run_fingerprint_test_task(test_id: int, profile_id: str = None,
                                   visit_external_sites: bool = False):
        """Sync Celery entry point for fingerprint test."""
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            run_fingerprint_collection(test_id, profile_id, visit_external_sites)
        )
