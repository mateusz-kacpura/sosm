import pytest
from pydantic import ValidationError

from app.models.schemas import (
    AccountCreate,
    AccountResponse,
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    GroupInput,
    GroupResponse,
    TaskLogResponse,
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
            groups=[GroupInput(url="https://fb.com/groups/1", content="Hello")],
        )
        assert campaign.name == "Test"
        assert campaign.base_interval_minutes == 60
        assert campaign.random_deviation_percent == 10.0
        assert len(campaign.groups) == 1
        assert campaign.groups[0].content == "Hello"

    def test_campaign_create_custom_interval(self):
        campaign = CampaignCreate(
            name="Test",
            account_id=1,
            groups=[GroupInput(url="url", content="content")],
            base_interval_minutes=30,
            random_deviation_percent=20.0,
        )
        assert campaign.base_interval_minutes == 30
        assert campaign.random_deviation_percent == 20.0

    def test_campaign_create_with_start_at(self):
        from datetime import datetime, timezone
        start = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        campaign = CampaignCreate(
            name="Test",
            account_id=1,
            groups=[GroupInput(url="url", content="content")],
            start_at=start,
        )
        assert campaign.start_at == start

    def test_campaign_create_missing_name(self):
        with pytest.raises(ValidationError):
            CampaignCreate(
                account_id=1,
                groups=[GroupInput(url="url", content="c")],
            )

    def test_campaign_create_missing_groups(self):
        with pytest.raises(ValidationError):
            CampaignCreate(name="Test", account_id=1)

    def test_campaign_create_empty_groups_allowed(self):
        campaign = CampaignCreate(
            name="Test",
            account_id=1,
            groups=[],
        )
        assert campaign.groups == []

    def test_campaign_update_valid(self):
        for status in ["SZKIC", "AKTYWNA", "WSTRZYMANA", "ZAKOŃCZONA", "BŁĄD"]:
            update = CampaignUpdate(status=status)
            assert update.status == status

    def test_campaign_update_missing_status(self):
        with pytest.raises(ValidationError):
            CampaignUpdate()


class TestGroupSchemas:
    def test_group_input_valid(self):
        g = GroupInput(url="https://fb.com/groups/1", content="Hello")
        assert g.url == "https://fb.com/groups/1"
        assert g.content == "Hello"
        assert g.media_urls is None

    def test_group_input_with_media(self):
        g = GroupInput(url="url", content="text", media_urls=["img.jpg"])
        assert g.media_urls == ["img.jpg"]

    def test_group_response_from_attributes(self):
        class FakeGroup:
            id = 1
            url = "https://fb.com/groups/1"
            name = "Test"
            content = "Hello"
            media_urls = None
            order = 0

        resp = GroupResponse.model_validate(FakeGroup(), from_attributes=True)
        assert resp.id == 1
        assert resp.content == "Hello"


class TestTaskLogSchemas:
    def test_task_log_response_all_fields(self):
        from datetime import datetime

        class FakeLog:
            id = 1
            group_id = 10
            campaign_name = "Campaign A"
            status = "SUCCESS"
            error_message = None
            screenshot_path = None
            planned_at = None
            retry_count = 0
            executed_at = datetime(2024, 1, 1)

        resp = TaskLogResponse.model_validate(FakeLog(), from_attributes=True)
        assert resp.id == 1
        assert resp.status == "SUCCESS"
        assert resp.campaign_name == "Campaign A"
        assert resp.retry_count == 0

    def test_task_log_response_with_error(self):
        from datetime import datetime

        class FakeLog:
            id = 2
            group_id = 10
            campaign_name = "Campaign B"
            status = "FAILED"
            error_message = "Connection timeout"
            screenshot_path = "/screenshots/error.png"
            planned_at = datetime(2024, 1, 1, 10, 0)
            retry_count = 3
            executed_at = datetime(2024, 1, 1)

        resp = TaskLogResponse.model_validate(FakeLog(), from_attributes=True)
        assert resp.error_message == "Connection timeout"
        assert resp.screenshot_path == "/screenshots/error.png"
        assert resp.retry_count == 3
