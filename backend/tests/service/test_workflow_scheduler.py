import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
from contextlib import asynccontextmanager

from app.models.workflow_models import Workflow, WorkflowRun
from tests.factories import WorkflowFactory, WorkflowRunFactory


@pytest.fixture
def mock_session_local(db_session):
    @asynccontextmanager
    async def factory():
        yield db_session

    return factory


class TestCheckScheduledWorkflows:
    async def test_no_active_workflows(self, db_session, mock_session_local):
        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()

    async def test_szkic_workflows_ignored(self, db_session, mock_session_local):
        wf = WorkflowFactory.create(
            status="SZKIC",
            schedule_type="interval",
            schedule_config={"interval_minutes": 10},
        )
        db_session.add(wf)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()

    async def test_manual_schedule_ignored(self, db_session, mock_session_local):
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="manual",
        )
        db_session.add(wf)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()

    async def test_interval_first_run(self, db_session, mock_session_local):
        """Workflow with interval schedule and no previous runs should trigger."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 60},
        )
        db_session.add(wf)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.core.scheduler.settings") as mock_settings:
                mock_settings.STANDALONE = True
                with patch("app.task_runner.submit_workflow_task", mock_submit):
                    from app.core.scheduler import check_scheduled_workflows
                    await check_scheduled_workflows()

        mock_submit.assert_called_once()

    async def test_interval_not_elapsed(self, db_session, mock_session_local):
        """Workflow shouldn't run if interval hasn't elapsed since last run."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 60},
        )
        db_session.add(wf)
        await db_session.flush()

        # Recent run (10 min ago)
        run = WorkflowRunFactory.create(
            workflow_id=wf.id,
            status="COMPLETED",
        )
        run.created_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_session.add(run)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()

    async def test_interval_elapsed(self, db_session, mock_session_local):
        """Workflow should run if interval has elapsed since last run."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 60},
        )
        db_session.add(wf)
        await db_session.flush()

        # Old run (2 hours ago)
        run = WorkflowRunFactory.create(
            workflow_id=wf.id,
            status="COMPLETED",
        )
        run.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        db_session.add(run)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.core.scheduler.settings") as mock_settings:
                mock_settings.STANDALONE = True
                with patch("app.task_runner.submit_workflow_task", mock_submit):
                    from app.core.scheduler import check_scheduled_workflows
                    await check_scheduled_workflows()

        mock_submit.assert_called_once()

    async def test_active_run_blocks_scheduling(self, db_session, mock_session_local):
        """Workflow with a RUNNING run should not be scheduled again."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 10},
        )
        db_session.add(wf)
        await db_session.flush()

        run = WorkflowRunFactory.create(
            workflow_id=wf.id,
            status="RUNNING",
        )
        db_session.add(run)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()

    async def test_pending_run_blocks_scheduling(self, db_session, mock_session_local):
        """Workflow with a PENDING run should not be scheduled again."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 10},
        )
        db_session.add(wf)
        await db_session.flush()

        run = WorkflowRunFactory.create(
            workflow_id=wf.id,
            status="PENDING",
        )
        db_session.add(run)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()

    async def test_creates_run_with_scheduled_trigger(self, db_session, mock_session_local):
        """Scheduled run should have trigger_type='scheduled'."""
        from sqlalchemy import select

        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 10},
        )
        db_session.add(wf)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.core.scheduler.settings") as mock_settings:
                mock_settings.STANDALONE = True
                with patch("app.task_runner.submit_workflow_task", mock_submit):
                    from app.core.scheduler import check_scheduled_workflows
                    await check_scheduled_workflows()

        result = await db_session.execute(
            select(WorkflowRun).where(WorkflowRun.workflow_id == wf.id)
        )
        run = result.scalar_one()
        assert run.trigger_type == "scheduled"
        assert run.status == "PENDING"

    async def test_null_schedule_type_ignored(self, db_session, mock_session_local):
        """Workflow with schedule_type=None should be ignored."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type=None,
        )
        db_session.add(wf)
        await db_session.flush()

        mock_submit = AsyncMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                from app.core.scheduler import check_scheduled_workflows
                await check_scheduled_workflows()

        mock_submit.assert_not_called()
