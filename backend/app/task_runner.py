"""Async task runner — replaces Celery + Redis for standalone mode.

Account-level locks prevent concurrent browser sessions.
Semaphore controls overall concurrency. Retries with exponential backoff.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_account_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_concurrency_semaphore: asyncio.Semaphore | None = None
_running_tasks: dict[str, asyncio.Task] = {}

RETRY_COUNTDOWNS = [5, 10, 20]


def init(max_concurrency: int = 10):
    global _concurrency_semaphore
    _concurrency_semaphore = asyncio.Semaphore(max_concurrency)
    logger.info("Task runner initialized (max_concurrency=%d)", max_concurrency)


async def submit_publish_task(
    account_id: int, account_email: str, account_pass: str,
    group_url: str, post_content: str, group_id: int,
    campaign_name: str = "", backup_cookies: dict = None,
    background_style: str = None, max_retries: int = 3,
):
    task = asyncio.create_task(
        _run_publish_with_retry(
            account_id, account_email, account_pass,
            group_url, post_content, group_id,
            campaign_name, backup_cookies, background_style,
            max_retries,
        )
    )
    task_key = f"publish:{group_id}:{datetime.now(timezone.utc).timestamp()}"
    _running_tasks[task_key] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_key, None))


async def _run_publish_with_retry(
    account_id, account_email, account_pass,
    group_url, post_content, group_id,
    campaign_name, backup_cookies, background_style,
    max_retries,
):
    from app.worker import run_bot_task

    lock = _account_locks[account_id]

    for attempt in range(max_retries + 1):
        async with lock:
            async with _concurrency_semaphore:
                try:
                    return await run_bot_task(
                        account_id, account_email, account_pass,
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
    test_id: int, account_id: int = None, visit_external_sites: bool = False,
):
    from app.worker import run_fingerprint_collection

    task = asyncio.create_task(
        run_fingerprint_collection(test_id, account_id, visit_external_sites)
    )
    task_key = f"fingerprint:{test_id}"
    _running_tasks[task_key] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_key, None))


async def submit_workflow_task(
    workflow_id: int, run_id: int,
    variables: dict = None, resume: bool = False,
):
    """Submit a workflow execution as an async task."""
    from app.workflow.executor import WorkflowExecutor

    executor = WorkflowExecutor()
    task = asyncio.create_task(
        executor.execute(workflow_id, run_id, variables, resume=resume)
    )
    task_key = f"workflow:{workflow_id}:{run_id}"
    _running_tasks[task_key] = task
    task.add_done_callback(lambda t: _running_tasks.pop(task_key, None))


async def cancel_workflow_task(workflow_id: int, run_id: int) -> bool:
    """Cancel a running workflow task via asyncio.Task.cancel().

    This raises CancelledError in the task, interrupting any asyncio.sleep()
    and allowing the executor's finally block to close the browser.
    """
    task_key = f"workflow:{workflow_id}:{run_id}"
    task = _running_tasks.get(task_key)
    if task and not task.done():
        task.cancel()
        logger.info("Cancelled workflow task %s", task_key)
        return True
    return False


def get_active_task_count() -> int:
    return len(_running_tasks)
