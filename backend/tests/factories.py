from datetime import datetime, timezone
from app.models.models import Account, Campaign, Group, TaskLog, FingerprintTest


class AccountFactory:
    _counter = 0

    @classmethod
    def create(cls, **overrides) -> Account:
        cls._counter += 1
        defaults = {
            "fb_email": f"fbuser{cls._counter}@example.com",
            "fb_password": "fbpassword123",
            "proxy_url": None,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return Account(**defaults)


class CampaignFactory:
    @staticmethod
    def create(**overrides) -> Campaign:
        defaults = {
            "name": "Test Campaign",
            "base_interval_minutes": 60,
            "random_deviation_percent": 10.0,
            "status": "SZKIC",
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return Campaign(**defaults)


class GroupFactory:
    @staticmethod
    def create(**overrides) -> Group:
        defaults = {
            "url": "https://facebook.com/groups/test-group",
            "name": "Test Group",
            "content": "Test post content",
            "media_urls": None,
            "order": 0,
        }
        defaults.update(overrides)
        return Group(**defaults)


class TaskLogFactory:
    @staticmethod
    def create(**overrides) -> TaskLog:
        defaults = {
            "campaign_name": "Test Campaign",
            "status": "SUCCESS",
            "error_message": None,
            "screenshot_path": None,
            "planned_at": None,
            "retry_count": 0,
            "executed_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return TaskLog(**defaults)


class FingerprintTestFactory:
    @staticmethod
    def create(**overrides) -> FingerprintTest:
        defaults = {
            "status": "PENDING",
            "proxy_url_used": None,
            "results": None,
            "error_message": None,
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
        defaults.update(overrides)
        return FingerprintTest(**defaults)
