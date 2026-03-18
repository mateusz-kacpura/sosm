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
        'check-scheduled-workflows-every-minute': {
            'task': 'app.worker.check_workflows_task',
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
from app.models import Account, Group, TaskLog, FingerprintTest, Fanpage
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


async def run_bot_task(account_id: int, account_email: str, account_pass: str,
                       group_url: str, post_content: str, group_id: int,
                       campaign_name: str = "",
                       backup_cookies: dict = None,
                       background_style: str = None):
    """Async: start browser (Camoufox via Donut profile), login + publish.
    Used by both Celery and standalone task runner."""
    async with AsyncSessionLocal() as db:
        try:
            # Lookup Donut Browser profile ID from account
            result = await db.execute(
                select(Account).where(Account.id == account_id)
            )
            account = result.scalars().first()
            donut_profile_id = account.browser_profile_id if account else None

            manager = BrowserManager(account_id, donut_profile_id=donut_profile_id)
            page = await manager.start(backup_cookies=backup_cookies)

            try:
                actions = FBActions(page, account_email)

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

                cookies = await manager.extract_session_cookies(page)
                if cookies:
                    result = await db.execute(
                        select(Account).where(Account.id == account_id)
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


async def run_fingerprint_collection(test_id: int, account_id: int = None,
                                      visit_external_sites: bool = False):
    """Async: start browser, collect fingerprint, analyze, store results."""
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

        # Use provided account_id or fallback to a default fingerprint account
        fp_account_id = account_id or settings.FINGERPRINT_ACCOUNT_ID or None

        # Fallback: use the only account if exactly one exists
        if not fp_account_id:
            all_accounts = (await db.execute(select(Account))).scalars().all()
            if len(all_accounts) == 1:
                fp_account_id = all_accounts[0].id

        # Lookup Donut Browser profile ID from account
        donut_profile_id = None
        if fp_account_id:
            acct_result = await db.execute(
                select(Account).where(Account.id == fp_account_id)
            )
            acct = acct_result.scalars().first()
            donut_profile_id = acct.browser_profile_id if acct else None

        try:
            manager = BrowserManager(fp_account_id, donut_profile_id=donut_profile_id)
            page = await manager.start()

            try:
                raw_data = await collect_fingerprint(page)
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
                            await page.goto(url)
                            await asyncio.sleep(8)
                            screenshot_path = os.path.join(screenshot_dir, f"fp_{test_id}_{site_key}.png")
                            await page.screenshot(path=screenshot_path)
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


async def run_fanpage_verification(fanpage_id: int, account_id: int):
    """Async: start browser, login, check if account manages the fanpage."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Fanpage).where(Fanpage.id == fanpage_id)
        )
        fanpage = result.scalars().first()
        if not fanpage:
            return

        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalars().first()
        if not account:
            fanpage.verification_status = "ERROR"
            fanpage.verification_error = "Account not found"
            await db.commit()
            return

        fanpage.verification_status = "RUNNING"
        await db.commit()

        donut_profile_id = account.browser_profile_id
        backup_cookies = account.session_cookies_backup

        try:
            manager = BrowserManager(account_id, donut_profile_id=donut_profile_id)
            page = await manager.start(backup_cookies=backup_cookies)

            try:
                actions = FBActions(page, account.fb_email)

                is_logged = await actions.login(account.fb_password)
                if not is_logged:
                    fanpage.verification_status = "ERROR"
                    fanpage.verification_error = "Login failed (checkpoint or session expired)"
                    await db.commit()
                    return

                verify_result = await actions.verify_fanpage_ownership(fanpage.fanpage_url)

                # Save cookies for session reuse
                cookies = await manager.extract_session_cookies(page)
                if cookies:
                    account.session_cookies_backup = cookies

                # Update fanpage name if extracted
                if verify_result.get("page_name"):
                    fanpage.fanpage_name = verify_result["page_name"]

                if verify_result.get("error"):
                    fanpage.verification_status = "ERROR"
                    fanpage.verification_error = verify_result["error"]
                elif verify_result["found"]:
                    fanpage.verification_status = "VERIFIED"
                    fanpage.verification_error = None
                    fanpage.verified_at = datetime.now(timezone.utc)
                else:
                    fanpage.verification_status = "FAILED"
                    fanpage.verification_error = "Fanpage not found in account's profile switcher"

                await db.commit()
            finally:
                await manager.stop()

        except Exception as e:
            fanpage.verification_status = "ERROR"
            fanpage.verification_error = str(e)[:500]
            await db.commit()
            logger.exception("Fanpage verification error for fanpage_id=%s", fanpage_id)


async def run_fanpage_discovery(account_id: int):
    """Async: start browser, login, discover all fanpages for account."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalars().first()
        if not account:
            return

        account.fanpage_discovery_status = "RUNNING"
        account.fanpage_discovery_error = None
        await db.commit()

        donut_profile_id = account.browser_profile_id
        backup_cookies = account.session_cookies_backup

        try:
            manager = BrowserManager(account_id, donut_profile_id=donut_profile_id)
            page = await manager.start(backup_cookies=backup_cookies)

            try:
                actions = FBActions(page, account.fb_email)

                is_logged = await actions.login(account.fb_password)
                if not is_logged:
                    account.fanpage_discovery_status = "ERROR"
                    account.fanpage_discovery_error = "Login failed (checkpoint or session expired)"
                    await db.commit()
                    return

                from app.bot.fanpage_discovery import discover_fanpages
                discovered = await discover_fanpages(actions)

                # Save cookies for session reuse
                cookies = await manager.extract_session_cookies(page)
                if cookies:
                    account.session_cookies_backup = cookies

                # Save discovered fanpages (skip duplicates)
                created_count = 0
                for fp_info in discovered:
                    url = fp_info["fanpage_url"]
                    name = fp_info.get("fanpage_name")

                    existing = await db.execute(
                        select(Fanpage).where(
                            Fanpage.account_id == account_id,
                            Fanpage.fanpage_url == url,
                        )
                    )
                    if existing.scalar_one_or_none():
                        logger.info("Fanpage already exists, skipping: %s", url)
                        continue

                    new_fanpage = Fanpage(
                        account_id=account_id,
                        fanpage_url=url,
                        fanpage_name=name,
                        verification_status="VERIFIED",
                        verified_at=datetime.now(timezone.utc),
                    )
                    db.add(new_fanpage)
                    created_count += 1

                account.fanpage_discovery_status = "COMPLETED"
                account.fanpage_discovery_error = None
                await db.commit()
                logger.info("Fanpage discovery completed for account %s: %d new fanpage(s)",
                            account_id, created_count)
            finally:
                await manager.stop()

        except Exception as e:
            account.fanpage_discovery_status = "ERROR"
            account.fanpage_discovery_error = str(e)[:500]
            await db.commit()
            logger.exception("Fanpage discovery error for account_id=%s", account_id)


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
    def publish_post_task(self, account_id: int, account_email: str, account_pass: str,
                          group_url: str, post_content: str, group_id: int,
                          campaign_name: str = "",
                          backup_cookies: dict = None,
                          background_style: str = None):
        """Sync Celery entry point — delegates to async browser code."""
        lock_key = f"sosm:account_lock:{account_id}"
        lock = _redis_client.lock(lock_key, timeout=_PROFILE_LOCK_TTL, blocking_timeout=120)
        if not lock.acquire(blocking=True):
            logger.warning("Account %s still locked after 120s, skipping", account_id)
            return None

        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            return loop.run_until_complete(
                run_bot_task(account_id, account_email, account_pass,
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
    def run_fingerprint_test_task(test_id: int, account_id: int = None,
                                   visit_external_sites: bool = False):
        """Sync Celery entry point for fingerprint test."""
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        loop.run_until_complete(
            run_fingerprint_collection(test_id, account_id, visit_external_sites)
        )

    @celery_app.task(name="app.worker.run_fanpage_verify_task")
    def run_fanpage_verify_task(fanpage_id: int, account_id: int):
        """Sync Celery entry point for fanpage verification."""
        lock_key = f"sosm:account_lock:{account_id}"
        lock = _redis_client.lock(lock_key, timeout=_PROFILE_LOCK_TTL, blocking_timeout=120)
        if not lock.acquire(blocking=True):
            logger.warning("Account %s still locked after 120s, skipping verification", account_id)
            return None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(
                run_fanpage_verification(fanpage_id, account_id)
            )
        finally:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    @celery_app.task(name="app.worker.run_fanpage_discovery_task")
    def run_fanpage_discovery_task(account_id: int):
        """Sync Celery entry point for fanpage discovery."""
        lock_key = f"sosm:account_lock:{account_id}"
        lock = _redis_client.lock(lock_key, timeout=_PROFILE_LOCK_TTL, blocking_timeout=120)
        if not lock.acquire(blocking=True):
            logger.warning("Account %s still locked after 120s, skipping discovery", account_id)
            return None
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(
                run_fanpage_discovery(account_id)
            )
        finally:
            try:
                lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    @celery_app.task(name="app.worker.check_workflows_task")
    def check_workflows_task():
        """Triggered by Celery Beat every minute — check scheduled workflows."""
        from app.core.scheduler import run_workflow_scheduler
        run_workflow_scheduler()

    @celery_app.task(name="app.worker.run_workflow_task")
    def run_workflow_task(workflow_id: int, run_id: int, variables: dict = None):
        """Sync Celery entry point for workflow execution."""
        from app.workflow.executor import WorkflowExecutor

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        executor = WorkflowExecutor()
        loop.run_until_complete(
            executor.execute(workflow_id, run_id, variables or {})
        )
