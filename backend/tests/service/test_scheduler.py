import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager

from app.models.models import Account, Campaign, Group, Post, TaskLog
from tests.factories import AccountFactory, CampaignFactory, GroupFactory, PostFactory, TaskLogFactory


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
        campaign = CampaignFactory.create(account_id=99999, status="W TOKU")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_campaign_without_posts_skipped(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="W TOKU")
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

        campaign = CampaignFactory.create(account_id=account.id, status="W TOKU")
        db_session.add(campaign)
        await db_session.flush()

        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_first_post_dispatched_immediately(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create(fb_email="dispatch@fb.com", fb_password="pass123")
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="W TOKU")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/test")
        db_session.add(group)
        post = PostFactory.create(campaign_id=campaign.id, content="First post!")
        db_session.add(post)
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
        assert call_kwargs["post_id"] == post.id

    async def test_successfully_published_post_skipped(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="W TOKU")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/done")
        db_session.add(group)
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        log = TaskLogFactory.create(
            post_id=post.id,
            group_url="https://fb.com/groups/done",
            status="SUCCESS",
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()

    async def test_failed_post_retried(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="W TOKU")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/fail")
        db_session.add(group)
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        log = TaskLogFactory.create(
            post_id=post.id,
            group_url="https://fb.com/groups/fail",
            status="FAILED",
        )
        db_session.add(log)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_called_once()

    async def test_interval_not_elapsed_skips_post(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="W TOKU",
            base_interval_minutes=60, random_deviation_percent=0.0,
        )
        db_session.add(campaign)
        await db_session.flush()

        group1 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g1")
        group2 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g2")
        db_session.add(group1)
        db_session.add(group2)

        post1 = PostFactory.create(campaign_id=campaign.id, content="Post 1")
        post2 = PostFactory.create(campaign_id=campaign.id, content="Post 2")
        db_session.add(post1)
        db_session.add(post2)
        await db_session.flush()

        # Post1 was successfully posted to g1 just 30 min ago
        log = TaskLogFactory.create(
            post_id=post1.id,
            group_url="https://fb.com/groups/g1",
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

    async def test_interval_elapsed_dispatches_post(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="W TOKU",
            base_interval_minutes=60, random_deviation_percent=0.0,
        )
        db_session.add(campaign)
        await db_session.flush()

        group1 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g1")
        group2 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/g2")
        db_session.add(group1)
        db_session.add(group2)

        post1 = PostFactory.create(campaign_id=campaign.id, content="Post 1")
        post2 = PostFactory.create(campaign_id=campaign.id, content="Post 2")
        db_session.add(post1)
        db_session.add(post2)
        await db_session.flush()

        # Post1 was successfully posted to g1 over 61 min ago
        log = TaskLogFactory.create(
            post_id=post1.id,
            group_url="https://fb.com/groups/g1",
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

    async def test_only_one_post_per_campaign_per_cycle(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="W TOKU")
        db_session.add(campaign)
        await db_session.flush()

        for i in range(3):
            group = GroupFactory.create(campaign_id=campaign.id, url=f"https://fb.com/groups/{i}")
            db_session.add(group)
        for i in range(3):
            post = PostFactory.create(campaign_id=campaign.id, content=f"Post {i}")
            db_session.add(post)
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
                account_id=account.id, status="W TOKU", name=f"Campaign {i}"
            )
            db_session.add(campaign)
            await db_session.flush()

            group = GroupFactory.create(campaign_id=campaign.id, url=f"https://fb.com/groups/c{i}")
            db_session.add(group)
            post = PostFactory.create(campaign_id=campaign.id, content=f"Content {i}")
            db_session.add(post)
            await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        assert mock_publish_task.delay.call_count == 2

    async def test_timezone_naive_log_handled(self, db_session, mock_publish_task, mock_session_local):
        """Tests lines 86-87: when last_log.executed_at.tzinfo is None."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(
            account_id=account.id, status="W TOKU",
            base_interval_minutes=60, random_deviation_percent=0.0,
        )
        db_session.add(campaign)
        await db_session.flush()

        group1 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/tz1")
        group2 = GroupFactory.create(campaign_id=campaign.id, url="https://fb.com/groups/tz2")
        db_session.add(group1)
        db_session.add(group2)

        post1 = PostFactory.create(campaign_id=campaign.id, content="TZ Post 1")
        post2 = PostFactory.create(campaign_id=campaign.id, content="TZ Post 2")
        db_session.add(post1)
        db_session.add(post2)
        await db_session.flush()

        # Create a SUCCESS log with timezone-naive datetime (no tzinfo)
        naive_time = datetime(2020, 1, 1, 12, 0, 0)  # no tzinfo
        log = TaskLogFactory.create(
            post_id=post1.id,
            group_url="https://fb.com/groups/tz1",
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

    async def test_oczekuje_campaigns_ignored(self, db_session, mock_publish_task, mock_session_local):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="OCZEKUJE")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        with patch("app.core.scheduler.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.publish_post_task", mock_publish_task):
                from app.core.scheduler import check_active_campaigns
                await check_active_campaigns()

        mock_publish_task.delay.assert_not_called()


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
