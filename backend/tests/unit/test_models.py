import pytest
from sqlalchemy import select

from app.models.models import Account, Campaign, Group, TaskLog
from tests.factories import (
    AccountFactory,
    CampaignFactory,
    GroupFactory,
    TaskLogFactory,
)


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

    async def test_account_campaigns_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        await db_session.refresh(account, ["campaigns"])
        assert len(account.campaigns) == 1


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

        campaign = Campaign(name="Defaults", account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        assert campaign.status == "SZKIC"

    async def test_campaign_default_interval(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = Campaign(name="Defaults", account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        assert campaign.base_interval_minutes == 60
        assert campaign.random_deviation_percent == 10.0

    async def test_campaign_start_at(self, db_session):
        from datetime import datetime, timezone
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        start = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
        campaign = CampaignFactory.create(account_id=account.id, start_at=start)
        db_session.add(campaign)
        await db_session.flush()

        assert campaign.start_at == start

    async def test_campaign_groups_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        for i in range(2):
            group = GroupFactory.create(
                campaign_id=campaign.id,
                url=f"https://fb.com/groups/{i}",
                content=f"Content {i}",
            )
            db_session.add(group)
        await db_session.flush()

        await db_session.refresh(campaign, ["groups"])
        assert len(campaign.groups) == 2


class TestGroupModel:
    async def test_group_with_content(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(
            campaign_id=campaign.id,
            content="Hello World",
            media_urls=["img.jpg"],
            order=3,
        )
        db_session.add(group)
        await db_session.flush()

        result = await db_session.execute(select(Group).where(Group.id == group.id))
        fetched = result.scalars().first()
        assert fetched.content == "Hello World"
        assert fetched.media_urls == ["img.jpg"]
        assert fetched.order == 3

    async def test_group_tasklogs_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        for i in range(2):
            log = TaskLogFactory.create(group_id=group.id)
            db_session.add(log)
        await db_session.flush()

        await db_session.refresh(group, ["task_logs"])
        assert len(group.task_logs) == 2
