import pytest
from pydantic import ValidationError

from app.models.schemas import (
    AccountCreate,
    AccountResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    PostResponse,
    TaskLogResponse,
    UserCreate,
)


class TestAccountSchemas:
    def test_account_create_valid(self):
        account = AccountCreate(
            fb_email="user@fb.com",
            fb_password="secret123",
            proxy_url="http://proxy:8080",
        )
        assert account.fb_email == "user@fb.com"
        assert account.fb_password == "secret123"
        assert account.proxy_url == "http://proxy:8080"

    def test_account_create_minimal(self):
        account = AccountCreate(fb_email="user@fb.com", fb_password="secret123")
        assert account.proxy_url is None

    def test_account_create_missing_password(self):
        with pytest.raises(ValidationError):
            AccountCreate(fb_email="user@fb.com")

    def test_account_create_missing_email(self):
        with pytest.raises(ValidationError):
            AccountCreate(fb_password="secret123")

    def test_account_response_from_attributes(self):
        class FakeAccount:
            id = 1
            fb_email = "user@fb.com"
            proxy_url = None
            created_at = "2024-01-01T00:00:00"

        resp = AccountResponse.model_validate(FakeAccount(), from_attributes=True)
        assert resp.id == 1
        assert resp.fb_email == "user@fb.com"


class TestCampaignSchemas:
    def test_campaign_create_valid(self):
        campaign = CampaignCreate(
            name="Test",
            account_id=1,
            groups=["https://fb.com/groups/1"],
            posts=["Hello world"],
        )
        assert campaign.name == "Test"
        assert campaign.base_interval_minutes == 60
        assert campaign.random_deviation_percent == 10.0

    def test_campaign_create_custom_interval(self):
        campaign = CampaignCreate(
            name="Test",
            account_id=1,
            groups=["url"],
            posts=["content"],
            base_interval_minutes=30,
            random_deviation_percent=20.0,
        )
        assert campaign.base_interval_minutes == 30
        assert campaign.random_deviation_percent == 20.0

    def test_campaign_create_missing_name(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                account_id=1,
                groups=["url"],
                posts=["content"],
            )

    def test_campaign_create_missing_groups(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                name="Test",
                account_id=1,
                posts=["content"],
            )

    def test_campaign_create_missing_posts(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                name="Test",
                account_id=1,
                groups=["url"],
            )

    def test_campaign_create_empty_groups_allowed(self):
        campaign = CampaignCreate(
            name="Test",
            account_id=1,
            groups=[],
            posts=["content"],
        )
        assert campaign.groups == []

    def test_campaign_update_valid(self):
        for status in ["OCZEKUJE", "W TOKU", "OPUBLIKOWANE", "ZATRZYMANE"]:
            update = CampaignUpdate(status=status)
            assert update.status == status

    def test_campaign_update_accepts_any_string(self):
        update = CampaignUpdate(status="INVALID")
        assert update.status == "INVALID"

    def test_campaign_update_missing_status(self):
        with pytest.raises(ValidationError):
            CampaignUpdate()


class TestPostSchemas:
    def test_post_response_from_attributes(self):
        class FakePost:
            id = 1
            content = "Hello"
            media_urls = None

        resp = PostResponse.model_validate(FakePost(), from_attributes=True)
        assert resp.id == 1
        assert resp.content == "Hello"
        assert resp.media_urls is None

    def test_post_response_with_media(self):
        class FakePost:
            id = 2
            content = "Post with images"
            media_urls = ["img1.jpg", "img2.jpg"]

        resp = PostResponse.model_validate(FakePost(), from_attributes=True)
        assert resp.media_urls == ["img1.jpg", "img2.jpg"]


class TestTaskLogSchemas:
    def test_task_log_response_all_fields(self):
        from datetime import datetime

        class FakeLog:
            id = 1
            post_id = 10
            group_url = "https://fb.com/groups/1"
            status = "SUCCESS"
            error_message = None
            screenshot_path = None
            executed_at = datetime(2024, 1, 1)

        resp = TaskLogResponse.model_validate(FakeLog(), from_attributes=True)
        assert resp.id == 1
        assert resp.status == "SUCCESS"
        assert resp.error_message is None

    def test_task_log_response_with_error(self):
        from datetime import datetime

        class FakeLog:
            id = 2
            post_id = 10
            group_url = "https://fb.com/groups/1"
            status = "FAILED"
            error_message = "Connection timeout"
            screenshot_path = "/screenshots/error.png"
            executed_at = datetime(2024, 1, 1)

        resp = TaskLogResponse.model_validate(FakeLog(), from_attributes=True)
        assert resp.error_message == "Connection timeout"
        assert resp.screenshot_path == "/screenshots/error.png"


class TestUserSchemas:
    def test_user_create_valid_email(self):
        user = UserCreate(email="valid@example.com", password="pass123")
        assert user.email == "valid@example.com"

    def test_user_create_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="pass123")
