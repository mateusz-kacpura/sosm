import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
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


class TestCeleryDispatch:
    """Tests verifying workflow dispatch via Celery in Docker (non-standalone) mode."""

    async def test_scheduler_dispatches_via_celery_in_docker_mode(
        self, db_session, mock_session_local
    ):
        """In Docker mode (STANDALONE=False), scheduler should call run_workflow_task.delay()."""
        wf = WorkflowFactory.create(
            status="AKTYWNY",
            schedule_type="interval",
            schedule_config={"interval_minutes": 10},
        )
        db_session.add(wf)
        await db_session.flush()

        mock_celery_task = MagicMock()
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.core.scheduler.settings") as mock_settings:
                mock_settings.STANDALONE = False
                with patch("app.worker.run_workflow_task", mock_celery_task):
                    from app.core.scheduler import check_scheduled_workflows
                    await check_scheduled_workflows()

        mock_celery_task.delay.assert_called_once()
        args = mock_celery_task.delay.call_args[0]
        assert args[0] == wf.id  # workflow_id
        assert args[2] == {}  # variables

    async def test_scheduler_dispatches_via_task_runner_in_standalone(
        self, db_session, mock_session_local
    ):
        """In standalone mode, scheduler should call submit_workflow_task()."""
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

        mock_submit.assert_called_once()
        args = mock_submit.call_args[0]
        assert args[0] == wf.id

    async def test_run_endpoint_dispatches_via_celery_in_docker_mode(self, client):
        """POST /workflows/{id}/run should dispatch via Celery in Docker mode."""
        from app.core.config import settings

        create_resp = await client.post(
            "/api/workflows/",
            json={
                "name": "Celery Test WF",
                "graph_data": {
                    "nodes": [
                        {"id": "n1", "type": "start", "position": {"x": 0, "y": 0},
                         "data": {"label": "Start", "config": {}}},
                        {"id": "n2", "type": "end", "position": {"x": 300, "y": 0},
                         "data": {"label": "End", "config": {}}},
                    ],
                    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                },
            },
        )
        assert create_resp.status_code == 200
        wf_id = create_resp.json()["id"]

        mock_celery_task = MagicMock()
        original = settings.STANDALONE
        try:
            settings.STANDALONE = False
            with patch("app.worker.run_workflow_task", mock_celery_task):
                resp = await client.post(f"/api/workflows/{wf_id}/run", json={})
        finally:
            settings.STANDALONE = original

        assert resp.status_code == 200
        mock_celery_task.delay.assert_called_once()
        assert mock_celery_task.delay.call_args[0][0] == wf_id

    async def test_run_endpoint_dispatches_via_task_runner_in_standalone(self, client):
        """POST /workflows/{id}/run should dispatch via task_runner in standalone mode."""
        from app.core.config import settings

        create_resp = await client.post(
            "/api/workflows/",
            json={
                "name": "Standalone Test WF",
                "graph_data": {
                    "nodes": [
                        {"id": "n1", "type": "start", "position": {"x": 0, "y": 0},
                         "data": {"label": "Start", "config": {}}},
                        {"id": "n2", "type": "end", "position": {"x": 300, "y": 0},
                         "data": {"label": "End", "config": {}}},
                    ],
                    "edges": [{"id": "e1", "source": "n1", "target": "n2"}],
                    "viewport": {"x": 0, "y": 0, "zoom": 1},
                },
            },
        )
        assert create_resp.status_code == 200
        wf_id = create_resp.json()["id"]

        mock_submit = AsyncMock()
        original = settings.STANDALONE
        try:
            settings.STANDALONE = True
            with patch("app.task_runner.submit_workflow_task", mock_submit):
                resp = await client.post(f"/api/workflows/{wf_id}/run", json={})
        finally:
            settings.STANDALONE = original

        assert resp.status_code == 200
        mock_submit.assert_called_once()


class TestCeleryBeatSchedule:
    """Verify that Celery Beat schedule includes workflow checker task."""

    def test_beat_schedule_has_workflow_checker(self):
        """beat_schedule should include check-scheduled-workflows-every-minute."""
        # Import the beat schedule config directly from the module
        # (only available when not standalone)
        from app.core.config import settings
        if settings.STANDALONE:
            pytest.skip("Beat schedule only in Docker mode")

        from app.worker import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "check-scheduled-workflows-every-minute" in schedule
        entry = schedule["check-scheduled-workflows-every-minute"]
        assert entry["task"] == "app.worker.check_workflows_task"
        assert entry["schedule"] == 60.0

    def test_beat_schedule_has_campaign_checker(self):
        """beat_schedule should include check-active-campaigns-every-minute."""
        from app.core.config import settings
        if settings.STANDALONE:
            pytest.skip("Beat schedule only in Docker mode")

        from app.worker import celery_app
        schedule = celery_app.conf.beat_schedule
        assert "check-active-campaigns-every-minute" in schedule
