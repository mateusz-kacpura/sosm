import pytest
from datetime import datetime, timezone
from tests.factories import AccountFactory, CampaignFactory, GroupFactory, TaskLogFactory


class TestGetStats:
    async def test_stats_empty_db(self, client):
        response = await client.get("/api/stats/")
        assert response.status_code == 200
        data = response.json()
        assert data["active_campaigns"] == 0
        assert data["total_accounts"] == 0
        assert data["posts_today"] == 0
        assert data["success_rate"] == "0%"

    async def test_stats_with_data(self, client, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        log = TaskLogFactory.create(
            group_id=group.id,
            status="SUCCESS",
            executed_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/stats/")
        data = response.json()
        assert data["active_campaigns"] == 1
        assert data["total_accounts"] == 1
        assert data["posts_today"] == 1
        assert data["success_rate"] == "100%"


class TestDeleteAccount:
    async def test_delete_account_success(self, client):
        resp = await client.post(
            "/api/accounts/",
            json={"fb_email": "delete@fb.com", "fb_password": "pass"},
        )
        account_id = resp.json()["id"]

        response = await client.delete(f"/api/accounts/{account_id}")
        assert response.status_code == 200
        assert response.json()["detail"] == "Account deleted"

        list_resp = await client.get("/api/accounts/")
        assert len(list_resp.json()) == 0

    async def test_delete_account_not_found(self, client):
        response = await client.delete("/api/accounts/99999")
        assert response.status_code == 404
