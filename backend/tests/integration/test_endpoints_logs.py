import pytest
from datetime import datetime, timezone, timedelta

from app.models.models import Account, Campaign, Group, TaskLog
from tests.factories import AccountFactory, CampaignFactory, GroupFactory, TaskLogFactory


class TestListLogs:
    async def test_list_logs_empty(self, client):
        response = await client.get("/api/logs/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_logs_returns_records(self, client, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        for i in range(3):
            log = TaskLogFactory.create(group_id=group.id)
            db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/logs/")
        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_list_logs_limited_to_100(self, client, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        for i in range(120):
            log = TaskLogFactory.create(
                group_id=group.id,
                executed_at=datetime.now(timezone.utc) + timedelta(seconds=i),
            )
            db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/logs/")
        assert response.status_code == 200
        assert len(response.json()) == 100

    async def test_list_logs_ordered_by_executed_at_desc(self, client, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        old_log = TaskLogFactory.create(
            group_id=group.id,
            campaign_name="Old",
            executed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        new_log = TaskLogFactory.create(
            group_id=group.id,
            campaign_name="New",
            executed_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        )
        db_session.add(old_log)
        db_session.add(new_log)
        await db_session.flush()

        response = await client.get("/api/logs/")
        logs = response.json()
        assert logs[0]["campaign_name"] == "New"
        assert logs[1]["campaign_name"] == "Old"

    async def test_list_logs_contains_new_fields(self, client, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        log = TaskLogFactory.create(
            group_id=group.id,
            campaign_name="Test",
            retry_count=2,
        )
        db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/logs/")
        data = response.json()[0]
        assert "group_id" in data
        assert "campaign_name" in data
        assert "retry_count" in data
        assert data["campaign_name"] == "Test"
        assert data["retry_count"] == 2
