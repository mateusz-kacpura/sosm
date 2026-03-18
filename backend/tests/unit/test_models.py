import pytest
from sqlalchemy import select

from app.models.models import Account, Fanpage, Campaign, Group, TaskLog
from tests.factories import (
    AccountFactory,
    FanpageFactory,
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


class TestFanpageModel:
    async def test_fanpage_creation(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        fanpage = FanpageFactory.create(account_id=account.id)
        db_session.add(fanpage)
        await db_session.flush()

        result = await db_session.execute(
            select(Fanpage).where(Fanpage.id == fanpage.id)
        )
        fetched = result.scalars().first()
        assert fetched is not None
        assert "facebook.com" in fetched.fanpage_url
        assert fetched.account_id == account.id

    async def test_fanpage_optional_name(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        fanpage = FanpageFactory.create(account_id=account.id, fanpage_name=None)
        db_session.add(fanpage)
        await db_session.flush()

        assert fanpage.fanpage_name is None

    async def test_account_fanpages_relationship(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        for i in range(3):
            fp = FanpageFactory.create(
                account_id=account.id,
                fanpage_url=f"https://facebook.com/fanpage{i}",
            )
            db_session.add(fp)
        await db_session.flush()

        await db_session.refresh(account, ["fanpages"])
        assert len(account.fanpages) == 3

    async def test_fanpage_cascade_delete(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        fanpage = FanpageFactory.create(account_id=account.id)
        db_session.add(fanpage)
        await db_session.flush()

        fanpage_id = fanpage.id
        await db_session.delete(account)
        await db_session.flush()

        result = await db_session.execute(
            select(Fanpage).where(Fanpage.id == fanpage_id)
        )
        assert result.scalars().first() is None


class TestAccountDiscoveryFields:
    async def test_default_discovery_status(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        result = await db_session.execute(
            select(Account).where(Account.id == account.id)
        )
        fetched = result.scalars().first()
        assert fetched.fanpage_discovery_status is None
        assert fetched.fanpage_discovery_error is None

    async def test_discovery_status_update(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        account.fanpage_discovery_status = "RUNNING"
        await db_session.flush()

        result = await db_session.execute(
            select(Account).where(Account.id == account.id)
        )
        fetched = result.scalars().first()
        assert fetched.fanpage_discovery_status == "RUNNING"

    async def test_discovery_completed_with_error_cleared(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        account.fanpage_discovery_status = "ERROR"
        account.fanpage_discovery_error = "Login failed"
        await db_session.flush()

        account.fanpage_discovery_status = "COMPLETED"
        account.fanpage_discovery_error = None
        await db_session.flush()

        result = await db_session.execute(
            select(Account).where(Account.id == account.id)
        )
        fetched = result.scalars().first()
        assert fetched.fanpage_discovery_status == "COMPLETED"
        assert fetched.fanpage_discovery_error is None

    async def test_discovery_error_stored(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        account.fanpage_discovery_status = "ERROR"
        account.fanpage_discovery_error = "Login failed (checkpoint or session expired)"
        await db_session.flush()

        result = await db_session.execute(
            select(Account).where(Account.id == account.id)
        )
        fetched = result.scalars().first()
        assert fetched.fanpage_discovery_status == "ERROR"
        assert fetched.fanpage_discovery_error == "Login failed (checkpoint or session expired)"


class TestFanpageVerificationFields:
    async def test_default_verification_status(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        fanpage = FanpageFactory.create(account_id=account.id)
        db_session.add(fanpage)
        await db_session.flush()

        result = await db_session.execute(
            select(Fanpage).where(Fanpage.id == fanpage.id)
        )
        fetched = result.scalars().first()
        assert fetched.verification_status == "UNVERIFIED"
        assert fetched.verification_error is None
        assert fetched.verified_at is None

    async def test_verification_status_update(self, db_session):
        from datetime import datetime, timezone

        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        fanpage = FanpageFactory.create(account_id=account.id)
        db_session.add(fanpage)
        await db_session.flush()

        fanpage.verification_status = "VERIFIED"
        fanpage.verified_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        await db_session.flush()

        result = await db_session.execute(
            select(Fanpage).where(Fanpage.id == fanpage.id)
        )
        fetched = result.scalars().first()
        assert fetched.verification_status == "VERIFIED"
        assert fetched.verified_at is not None

    async def test_verification_error_stored(self, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        fanpage = FanpageFactory.create(account_id=account.id)
        db_session.add(fanpage)
        await db_session.flush()

        fanpage.verification_status = "FAILED"
        fanpage.verification_error = "Fanpage not found in profile switcher"
        await db_session.flush()

        result = await db_session.execute(
            select(Fanpage).where(Fanpage.id == fanpage.id)
        )
        fetched = result.scalars().first()
        assert fetched.verification_status == "FAILED"
        assert fetched.verification_error == "Fanpage not found in profile switcher"


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

        assert campaign.base_interval_minutes == 840
        assert campaign.random_deviation_percent == 20.0
        assert campaign.posts_per_day == 1

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
