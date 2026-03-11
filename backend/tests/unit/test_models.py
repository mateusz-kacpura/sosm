import pytest
from sqlalchemy import select

from app.models.models import User, Account, Campaign, Group, Post, TaskLog
from tests.factories import (
    UserFactory,
    AccountFactory,
    CampaignFactory,
    GroupFactory,
    PostFactory,
    TaskLogFactory,
)


class TestUserModel:
    async def test_user_creation(self, db_session):
        user = UserFactory.create(email="dbtest@example.com")
        db_session.add(user)
        await db_session.flush()

        result = await db_session.execute(select(User).where(User.id == user.id))
        fetched = result.scalars().first()
        assert fetched is not None
        assert fetched.email == "dbtest@example.com"
        assert fetched.is_active is True

    async def test_user_accounts_relationship(self, db_session):
        user = UserFactory.create(email="rel@example.com")
        db_session.add(user)
        await db_session.flush()

        account = AccountFactory.create(user_id=user.id)
        db_session.add(account)
        await db_session.flush()

        await db_session.refresh(user, ["accounts"])
        assert len(user.accounts) == 1
        assert user.accounts[0].fb_email == account.fb_email


class TestAccountModel:
    async def test_account_creation(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        result = await db_session.execute(
            select(Account).where(Account.id == account.id)
        )
        fetched = result.scalars().first()
        assert fetched is not None
        assert fetched.fb_password == "fbpassword123"

    async def test_account_owner_relationship(self, db_session):
        user = UserFactory.create(email="owner@example.com")
        db_session.add(user)
        await db_session.flush()

        account = AccountFactory.create(user_id=user.id)
        db_session.add(account)
        await db_session.flush()

        await db_session.refresh(account, ["owner"])
        assert account.owner.email == "owner@example.com"


class TestCampaignModel:
    async def test_campaign_creation(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        result = await db_session.execute(
            select(Campaign).where(Campaign.id == campaign.id)
        )
        fetched = result.scalars().first()
        assert fetched is not None
        assert fetched.name == "Test Campaign"

    async def test_campaign_default_status(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = Campaign(
            name="Defaults",
            account_id=account.id,
        )
        db_session.add(campaign)
        await db_session.flush()

        assert campaign.status == "OCZEKUJE"

    async def test_campaign_default_interval(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = Campaign(name="Defaults", account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        assert campaign.base_interval_minutes == 60
        assert campaign.random_deviation_percent == 10.0

    async def test_campaign_posts_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        for i in range(3):
            post = PostFactory.create(campaign_id=campaign.id, content=f"Post {i}")
            db_session.add(post)
        await db_session.flush()

        await db_session.refresh(campaign, ["posts"])
        assert len(campaign.posts) == 3

    async def test_campaign_groups_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        for i in range(2):
            group = GroupFactory.create(
                campaign_id=campaign.id, url=f"https://fb.com/groups/{i}"
            )
            db_session.add(group)
        await db_session.flush()

        await db_session.refresh(campaign, ["groups"])
        assert len(campaign.groups) == 2


class TestPostModel:
    async def test_post_tasklogs_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        post = PostFactory.create(campaign_id=campaign.id)
        db_session.add(post)
        await db_session.flush()

        for i in range(2):
            log = TaskLogFactory.create(
                post_id=post.id, group_url=f"https://fb.com/groups/{i}"
            )
            db_session.add(log)
        await db_session.flush()

        await db_session.refresh(post, ["tasks"])
        assert len(post.tasks) == 2
