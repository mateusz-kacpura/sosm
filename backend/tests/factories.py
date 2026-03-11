from datetime import datetime, timezone
from app.models.models import User, Account, Campaign, Group, Post, TaskLog


class UserFactory:
    _counter = 0

    @classmethod
    def create(cls, **overrides) -> User:
        cls._counter += 1
        defaults = {
            "email": f"test{cls._counter}@example.com",
            "hashed_password": "hashedpassword123",
            "is_active": True,
            "created_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return User(**defaults)


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
            "status": "OCZEKUJE",
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
        }
        defaults.update(overrides)
        return Group(**defaults)


class PostFactory:
    @staticmethod
    def create(**overrides) -> Post:
        defaults = {
            "content": "Test post content",
            "media_urls": None,
        }
        defaults.update(overrides)
        return Post(**defaults)


class TaskLogFactory:
    @staticmethod
    def create(**overrides) -> TaskLog:
        defaults = {
            "group_url": "https://facebook.com/groups/test-group",
            "status": "SUCCESS",
            "error_message": None,
            "screenshot_path": None,
            "executed_at": datetime.now(timezone.utc),
        }
        defaults.update(overrides)
        return TaskLog(**defaults)
