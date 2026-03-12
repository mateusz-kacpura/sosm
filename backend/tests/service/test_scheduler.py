import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app.models.models import Account, Campaign, Group, TaskLog
from tests.factories import AccountFactory, CampaignFactory, GroupFactory, TaskLogFactory


@pytest.fixture
def mock_publish_task():
    mock = MagicMock()
    mock.delay = MagicMock()
    return mock


@pytest.fixture
def mock_session_local(db_session):
    @asynccontextmanager
    async def factory():
        yield db_session

    return factory


class TestCheckActiveCampaigns:
    async def test_no_active_campaigns(self, db_session, mock_publish_task, mock_session_local):
        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_campaign_without_account_skipped(self, db_session, mock_publish_task, mock_session_local):
        campaign = CampaignFactory.create(account_id=99999, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_campaign_without_scheduled_groups_skipped(self, db_session, mock_publish_task, mock_session_local):
        """Groups without planned_at are ignored by the scheduler."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        # Group without planned_at
        group = GroupFactory.create(campaign_id=campaign.id, planned_at=None)
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_group_with_past_planned_at_dispatched(self, db_session, mock_publish_task, mock_session_local):
        """Group with planned_at in the past should be dispatched."""
        account = AccountFactory.create(
            fb_email="dispatch@fb.com", fb_password="pass123",
            browser_profile_id="profile_abc", session_cookies_backup={"c_user": "123"},
        )
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA", name="Test Camp")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            url="https://fb.com/groups/test",
            content="First post!",
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()
        call_kwargs = mock_publish_task.delay.call_args[1]
        assert call_kwargs["profile_id"] == "profile_abc"
        assert call_kwargs["account_email"] == "dispatch@fb.com"
        assert call_kwargs["account_pass"] == "pass123"
        assert call_kwargs["group_url"] == "https://fb.com/groups/test"
        assert call_kwargs["post_content"] == "First post!"
        assert call_kwargs["group_id"] == group.id
        assert call_kwargs["campaign_name"] == "Test Camp"
        assert call_kwargs["backup_cookies"] == {"c_user": "123"}

    async def test_group_with_future_planned_at_not_dispatched(self, db_session, mock_publish_task, mock_session_local):
        """Group with planned_at in the future should NOT be dispatched."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_successfully_published_group_skipped(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            url="https://fb.com/groups/done",
            planned_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(group)
        await db_session.flush()

        log = TaskLogFactory.create(group_id=group.id, status="SUCCESS")
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_failed_group_retried(self, db_session, mock_publish_task, mock_session_local):
        """Group with FAILED log (not SUCCESS) should be retried."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            url="https://fb.com/groups/fail",
            planned_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db_session.add(group)
        await db_session.flush()

        log = TaskLogFactory.create(group_id=group.id, status="FAILED")
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()

    async def test_in_flight_task_blocks_campaign(self, db_session, mock_publish_task, mock_session_local):
        """Recent QUEUED log within 5 min cutoff should block further dispatch."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        # Recent QUEUED log (2 min ago — within 5 min cutoff)
        log = TaskLogFactory.create(
            group_id=group.id,
            status="QUEUED",
            executed_at=datetime.now(timezone.utc) - timedelta(minutes=2),
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_old_queued_log_allows_retry(self, db_session, mock_publish_task, mock_session_local):
        """QUEUED log older than 5 min should not block dispatch."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        # Old QUEUED log (10 min ago — outside 5 min cutoff)
        log = TaskLogFactory.create(
            group_id=group.id,
            status="QUEUED",
            executed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()

    async def test_only_one_group_per_campaign_per_cycle(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        for i in range(3):
            group = GroupFactory.create(
                campaign_id=campaign.id,
                url=f"https://fb.com/groups/{i}",
                content=f"Content {i}",
                planned_at=datetime.now(timezone.utc) - timedelta(minutes=30 - i),
            )
            db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        assert mock_publish_task.delay.call_count == 1

    async def test_multiple_campaigns_processed(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        for i in range(2):
            campaign = CampaignFactory.create(
                account_id=account.id, status="AKTYWNA", name=f"Campaign {i}"
            )
            db_session.add(campaign)
            await db_session.flush()

            group = GroupFactory.create(
                campaign_id=campaign.id,
                url=f"https://fb.com/groups/c{i}",
                content=f"Content {i}",
                planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            )
            db_session.add(group)
            await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        assert mock_publish_task.delay.call_count == 2

    async def test_szkic_campaigns_ignored(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="SZKIC")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_start_at_future_skips_campaign(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        future = datetime.now(timezone.utc) + timedelta(hours=2)
        campaign = CampaignFactory.create(
            account_id=account.id, status="AKTYWNA", start_at=future,
        )
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_start_at_past_processes_campaign(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        campaign = CampaignFactory.create(
            account_id=account.id, status="AKTYWNA", start_at=past,
        )
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()

    async def test_start_at_none_processes_immediately(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="AKTYWNA", start_at=None,
        )
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()

    async def test_creates_queued_log_on_dispatch(self, db_session, mock_publish_task, mock_session_local):
        """Scheduler creates a QUEUED TaskLog when dispatching."""
        from sqlalchemy import select

        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        result = await db_session.execute(
            select(TaskLog).where(TaskLog.group_id == group.id, TaskLog.status == "QUEUED")
        )
        queued_log = result.scalars().first()
        assert queued_log is not None
        assert queued_log.campaign_name == campaign.name


class TestCampaignAutoComplete:
    """Tests for auto-marking campaigns as ZAKOŃCZONA."""

    async def test_all_groups_done_marks_campaign_finished(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        # All groups have SUCCESS logs
        for i in range(3):
            group = GroupFactory.create(
                campaign_id=campaign.id,
                planned_at=datetime.now(timezone.utc) - timedelta(hours=i + 1),
            )
            db_session.add(group)
            await db_session.flush()

            log = TaskLogFactory.create(group_id=group.id, status="SUCCESS")
            db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        await db_session.refresh(campaign)
        assert campaign.status == "ZAKOŃCZONA"
        mock_publish_task.delay.assert_not_called()

    async def test_not_all_groups_done_stays_active(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        # Group 1: done
        group1 = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
        db_session.add(group1)
        await db_session.flush()
        log1 = TaskLogFactory.create(group_id=group1.id, status="SUCCESS")
        db_session.add(log1)

        # Group 2: pending (future planned_at)
        group2 = GroupFactory.create(
            campaign_id=campaign.id,
            planned_at=datetime.now(timezone.utc) + timedelta(hours=2),
        )
        db_session.add(group2)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        await db_session.refresh(campaign)
        assert campaign.status == "AKTYWNA"

    async def test_no_groups_does_not_mark_finished(self, db_session, mock_publish_task, mock_session_local):
        """Campaign with zero groups should not be marked ZAKOŃCZONA."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        await db_session.refresh(campaign)
        assert campaign.status == "AKTYWNA"


class TestRunCampaignScheduler:
    def test_run_campaign_scheduler_calls_check_active(self):
        with patch("app.core.scheduler.check_active_campaigns", new_callable=AsyncMock) as mock_check:
            from app.core.scheduler import run_campaign_scheduler
            run_campaign_scheduler()
            mock_check.assert_called_once()

    def test_run_campaign_scheduler_creates_loop_if_closed(self):
        import asyncio

        closed_loop = asyncio.new_event_loop()
        closed_loop.close()

        with patch("app.core.scheduler.check_active_campaigns", new_callable=AsyncMock) as mock_check:
            with patch("app.core.scheduler.asyncio.get_event_loop", return_value=closed_loop):
                from app.core.scheduler import run_campaign_scheduler
                run_campaign_scheduler()
                mock_check.assert_called_once()
