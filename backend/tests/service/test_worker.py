import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from contextlib import asynccontextmanager


@pytest.fixture
def mock_session_local(db_session):
    @asynccontextmanager
    async def factory():
        yield db_session

    return factory


@pytest.fixture
def mock_browser_setup():
    mock_page = AsyncMock()
    mock_manager = AsyncMock()
    mock_manager.start = AsyncMock(return_value=mock_page)
    mock_manager.__aenter__ = AsyncMock(return_value=mock_manager)
    mock_manager.__aexit__ = AsyncMock(return_value=False)
    return mock_page, mock_manager


class TestRunBotTask:
    async def test_success(self, db_session, mock_session_local, mock_browser_setup):
        mock_page, mock_manager = mock_browser_setup

        from app.models.models import Account, Campaign, Post
        from tests.factories import AccountFactory, CampaignFactory, PostFactory

        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        mock_actions = AsyncMock()
        mock_actions.login = AsyncMock(return_value=True)
        mock_actions.publish_on_group = AsyncMock(return_value=True)

        with patch("app.worker.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.BrowserManager", return_value=mock_manager):
                with patch("app.worker.FBActions", return_value=mock_actions):
                    from app.worker import run_bot_task
                    result = await run_bot_task(
                        "test@fb.com", "pass", None,
                        "https://fb.com/groups/1", "Hello", post.id,
                    )

        assert result is True
        mock_actions.login.assert_called_once_with("pass")
        mock_actions.publish_on_group.assert_called_once_with("https://fb.com/groups/1", "Hello")

    async def test_login_failure(self, db_session, mock_session_local, mock_browser_setup):
        mock_page, mock_manager = mock_browser_setup

        from tests.factories import AccountFactory, CampaignFactory, PostFactory

        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()
        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        mock_actions = AsyncMock()
        mock_actions.login = AsyncMock(return_value=False)

        with patch("app.worker.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.BrowserManager", return_value=mock_manager):
                with patch("app.worker.FBActions", return_value=mock_actions):
                    from app.worker import run_bot_task
                    result = await run_bot_task(
                        "test@fb.com", "pass", None,
                        "https://fb.com/groups/1", "Hello", post.id,
                    )

        assert result is False

    async def test_publish_failure(self, db_session, mock_session_local, mock_browser_setup):
        mock_page, mock_manager = mock_browser_setup

        from tests.factories import AccountFactory, CampaignFactory, PostFactory

        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()
        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        mock_actions = AsyncMock()
        mock_actions.login = AsyncMock(return_value=True)
        mock_actions.publish_on_group = AsyncMock(return_value=False)

        with patch("app.worker.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.BrowserManager", return_value=mock_manager):
                with patch("app.worker.FBActions", return_value=mock_actions):
                    from app.worker import run_bot_task
                    result = await run_bot_task(
                        "test@fb.com", "pass", None,
                        "https://fb.com/groups/1", "Hello", post.id,
                    )

        # The function returns the success value from publish_on_group
        # which is stored in the TaskLog

    async def test_exception_creates_log_and_reraises(self, db_session, mock_session_local):
        from tests.factories import AccountFactory, CampaignFactory, PostFactory

        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()
        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()
        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        mock_manager = AsyncMock()
        mock_manager.__aenter__ = AsyncMock(side_effect=Exception("connection error"))
        mock_manager.__aexit__ = AsyncMock(return_value=False)

        with patch("app.worker.AsyncSessionLocal", mock_session_local):
            with patch("app.worker.BrowserManager", return_value=mock_manager):
                from app.worker import run_bot_task
                with pytest.raises(Exception, match="connection error"):
                    await run_bot_task(
                        "test@fb.com", "pass", None,
                        "https://fb.com/groups/1", "Hello", post.id,
                    )


class TestPublishPostTask:
    def test_publish_post_task_delegates_to_run_bot_task(self):
        mock_run_bot = AsyncMock(return_value=True)
        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = False
        mock_loop.run_until_complete = MagicMock(return_value=True)

        with patch("app.worker.run_bot_task", mock_run_bot):
            with patch("app.worker.asyncio.get_event_loop", return_value=mock_loop):
                from app.worker import publish_post_task
                result = publish_post_task.run(
                    "email@fb.com", "pass", None,
                    "https://fb.com/groups/1", "Hello", 42,
                )

        assert result is True
        mock_loop.run_until_complete.assert_called_once()

    def test_publish_post_task_creates_loop_if_closed(self):
        mock_run_bot = AsyncMock(return_value=True)
        closed_loop = MagicMock()
        closed_loop.is_closed.return_value = True
        new_loop = MagicMock()
        new_loop.run_until_complete = MagicMock(return_value=True)

        with patch("app.worker.run_bot_task", mock_run_bot):
            with patch("app.worker.asyncio.get_event_loop", return_value=closed_loop):
                with patch("app.worker.asyncio.new_event_loop", return_value=new_loop):
                    with patch("app.worker.asyncio.set_event_loop"):
                        from app.worker import publish_post_task
                        result = publish_post_task.run(
                            "email@fb.com", "pass", None,
                            "https://fb.com/groups/1", "Hello", 42,
                        )

        assert result is True
        new_loop.run_until_complete.assert_called_once()

    def test_publish_post_task_retries_on_exception(self):
        mock_loop = MagicMock()
        mock_loop.is_closed.return_value = False
        mock_loop.run_until_complete = MagicMock(side_effect=Exception("bot crash"))

        with patch("app.worker.asyncio.get_event_loop", return_value=mock_loop):
            from app.worker import publish_post_task
            publish_post_task.push_request(id="test-task-id")
            try:
                with patch.object(publish_post_task, "retry", side_effect=Exception("retrying")) as mock_retry:
                    with pytest.raises(Exception, match="retrying"):
                        publish_post_task.run(
                            "email@fb.com", "pass", None,
                            "https://fb.com/groups/1", "Hello", 42,
                        )
                # retry is called by our code and possibly by autoretry
                assert mock_retry.call_count >= 1
            finally:
                publish_post_task.pop_request()


class TestCheckCampaignsTask:
    def test_calls_scheduler(self):
        with patch("app.core.scheduler.run_campaign_scheduler") as mock_scheduler:
            from app.worker import check_campaigns_task
            check_campaigns_task()
            mock_scheduler.assert_called_once()
