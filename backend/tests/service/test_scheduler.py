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

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_campaign_without_groups_skipped(self, db_session, mock_publish_task, mock_session_local):
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

        mock_publish_task.delay.assert_not_called()

    async def test_first_group_dispatched_immediately(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create(fb_email="dispatch@fb.com", fb_password="pass123")
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA", name="Test Camp")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            url="https://fb.com/groups/test",
            content="First post!",
        )
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()
        call_kwargs = mock_publish_task.delay.call_args[1]
        assert call_kwargs["account_email"] == "dispatch@fb.com"
        assert call_kwargs["account_pass"] == "pass123"
        assert call_kwargs["group_url"] == "https://fb.com/groups/test"
        assert call_kwargs["post_content"] == "First post!"
        assert call_kwargs["group_id"] == group.id
        assert call_kwargs["campaign_name"] == "Test Camp"

    async def test_successfully_published_group_skipped(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/done")
        db_session.add(group)
        await db_session.flush()

        log = TaskLogFactory.create(
            group_id=group.id,
            status="SUCCESS",
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_failed_group_retried(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/fail")
        db_session.add(group)
        await db_session.flush()

        log = TaskLogFactory.create(
            group_id=group.id,
            status="FAILED",
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()

    async def test_interval_not_elapsed_skips_group(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="AKTYWNA",
            base_interval_minutes=60, random_deviation_percent=0.0,
        )
        db_session.add(campaign)
        await db_session.flush()

        group1 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g1", content="Content 1")
        group2 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g2", content="Content 2")
        db_session.add(group1)
        db_session.add(group2)
        await db_session.flush()

        # group1 was successfully posted 30 min ago (interval is 60 min)
        log = TaskLogFactory.create(
            group_id=group1.id,
            status="SUCCESS",
            executed_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                with patch("app.core.scheduler.random.uniform", return_value=0):
                    from app.core.scheduler import check_active_campaigns
                    await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_interval_elapsed_dispatches_group(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="AKTYWNA",
            base_interval_minutes=60, random_deviation_percent=0.0,
        )
        db_session.add(campaign)
        await db_session.flush()

        group1 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g1", content="Content 1")
        group2 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g2", content="Content 2")
        db_session.add(group1)
        db_session.add(group2)
        await db_session.flush()

        # group1 was successfully posted over 61 min ago
        log = TaskLogFactory.create(
            group_id=group1.id,
            status="SUCCESS",
            executed_at=datetime.now(timezone.utc) - timedelta(minutes=61),
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                with patch("app.core.scheduler.random.uniform", return_value=0):
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
            )
            db_session.add(group)
            await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        assert mock_publish_task.delay.call_count == 2

    async def test_timezone_naive_log_handled(self, db_session, mock_publish_task, mock_session_local):
        """Tests when last_log.executed_at.tzinfo is None."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="AKTYWNA",
            base_interval_minutes=60, random_deviation_percent=0.0,
        )
        db_session.add(campaign)
        await db_session.flush()

        group1 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/tz1", content="TZ Content 1")
        group2 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/tz2", content="TZ Content 2")
        db_session.add(group1)
        db_session.add(group2)
        await db_session.flush()

        # Create a SUCCESS log with timezone-naive datetime (no tzinfo)
        naive_time = datetime(2020, 1, 1, 12, 0, 0)  # no tzinfo
        log = TaskLogFactory.create(
            group_id=group1.id,
            status="SUCCESS",
            executed_at=naive_time,
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                with patch("app.core.scheduler.random.uniform", return_value=0):
                    from app.core.scheduler import check_active_campaigns
                    await check_active_campaigns()

        # The naive datetime was long ago, so it should dispatch
        mock_publish_task.delay.assert_called_once()

    async def test_szkic_campaigns_ignored(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="SZKIC")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
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

        group = GroupFactory.create(campaign_id=campaign.id)
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

        group = GroupFactory.create(campaign_id=campaign.id)
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

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()


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
