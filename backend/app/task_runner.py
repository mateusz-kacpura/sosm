"""Async task runner — replaces Celery + Redis for standalone mode.

Profile-level locks prevent concurrent browser sessions.
Semaphore controls overall concurrency. Retries with exponential backoff.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_profile_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_concurrency_semaphore: asyncio.Semaphore | None = None
_running_tasks: dict[str, asyncio.Task] = {}

RETRY_COUNTDOWNS = [5, 10, 20]


def init(max_concurrency: int = 10):
    global _concurrency_semaphore
    _concurrency_semaphore = asyncio.Semaphore(max_concurrency)
    logger.info("Task runner initialized (max_concurrency=%d)", max_concurrency)


async def submit_publish_task(
    profile_id: str, account_email: str, account_pass: str,
    group_url: str, post_content: str, group_id: int,
    campaign_name: str = "", backup_cookies: dict = None,
    background_style: str = None, max_retries: int = 3,
):
    task = asyncio.create_task(
        _run_publish_with_retry(
            profile_id, account_email, account_pass,
            group_url, post_content, group_id,
            campaign_name, backup_cookies, background_style,
            max_retries,
        )
    )
    task_key = f"publish:{group_id}:{datetime.now(timezone.utc).timestamp()}"
    _running_tasks[task_key] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_key, None))


async def _run_publish_with_retry(
    profile_id, account_email, account_pass,
    group_url, post_content, group_id,
    campaign_name, backup_cookies, background_style,
    max_retries,
):
    from app.worker import run_bot_task

    lock = _profile_locks[profile_id]

    for attempt in range(max_retries + 1):
        async with lock:
            async with _concurrency_semaphore:
                try:
                    return await run_bot_task(
                        profile_id, account_email, account_pass,
                        group_url, post_content, group_id,
                        campaign_name, backup_cookies, background_style,
                    )
                except Exception as exc:
                    if attempt < max_retries:
                        delay = RETRY_COUNTDOWNS[attempt] if attempt < len(RETRY_COUNTDOWNS) else 20
                        logger.warning(
                            "Publish task failed (attempt %d/%d), retry in %ds: %s",
                            attempt + 1, max_retries, delay, exc,
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error("Publish task failed after %d retries: %s", max_retries, exc)
                        raise


async def submit_fingerprint_task(
    test_id: int, profile_id: str = None, visit_external_sites: bool = False,
):
    from app.worker import run_fingerprint_collection

    task = asyncio.create_task(
        run_fingerprint_collection(test_id, profile_id, visit_external_sites)
    )
    task_key = f"fingerprint:{test_id}"
    _running_tasks[task_key] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_key, None))


def get_active_task_count() -> int:
    return len(_running_tasks)
