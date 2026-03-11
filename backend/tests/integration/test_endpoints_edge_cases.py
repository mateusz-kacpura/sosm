import pytest
from datetime import datetime, timezone
from tests.factories import AccountFactory, CampaignFactory, GroupFactory, TaskLogFactory


async def create_test_account(client):
    resp = await client.post(
        "/api/accounts/",
        json={"fb_email": "edge@fb.com", "fb_password": "pass"},
    )
    return resp.json()["id"]


class TestDeleteAccountCascade:
    async def test_delete_account_with_campaigns(self, client, db_session):
        """Deleting account that has campaigns should work."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        response = await client.delete(f"/api/accounts/{account.id}")
        assert response.status_code == 200

    async def test_delete_account_invalid_id_type(self, client):
        response = await client.delete("/api/accounts/abc")
        assert response.status_code == 422


class TestStatsEdgeCases:
    async def test_stats_success_rate_rounding(self, client, db_session):
        """Success rate with mixed results should round correctly."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id, status="AKTYWNA")
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        # 2 success, 1 failed = 67%
        for status in ["SUCCESS", "SUCCESS", "FAILED"]:
            log = TaskLogFactory.create(
                group_id=group.id,
                status=status,
                executed_at=datetime.now(timezone.utc),
            )
            db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/stats/")
        data = response.json()
        assert data["success_rate"] == "67%"
        assert data["active_campaigns"] == 1

    async def test_stats_only_counts_today_posts(self, client, db_session):
        """posts_today should only count today's SUCCESS logs."""
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        # Old log (yesterday) - should not count
        old_log = TaskLogFactory.create(
            group_id=group.id,
            status="SUCCESS",
            executed_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(old_log)

        # Today's log
        today_log = TaskLogFactory.create(
            group_id=group.id,
            status="SUCCESS",
            executed_at=datetime.now(timezone.utc),
        )
        db_session.add(today_log)
        await db_session.flush()

        response = await client.get("/api/stats/")
        data = response.json()
        assert data["posts_today"] == 1

    async def test_stats_failed_not_counted_as_posts_today(self, client, db_session):
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
            status="FAILED",
            executed_at=datetime.now(timezone.utc),
        )
        db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/stats/")
        assert response.json()["posts_today"] == 0


class TestCampaignGroupsWithContent:
    async def test_groups_preserve_content_and_order(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "Content Test",
                "account_id": account_id,
                "groups": [
                    {"url": "https://fb.com/groups/a", "content": "First content"},
                    {"url": "https://fb.com/groups/b", "content": "Second content"},
                ],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.get(f"/api/campaigns/{campaign_id}/groups")
        data = response.json()
        assert data[0]["content"] == "First content"
        assert data[0]["order"] == 0
        assert data[1]["content"] == "Second content"
        assert data[1]["order"] == 1

    async def test_groups_with_media_urls(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "Media Test",
                "account_id": account_id,
                "groups": [
                    {
                        "url": "https://fb.com/groups/media",
                        "content": "Post with media",
                        "media_urls": ["img1.jpg", "img2.png"],
                    },
                ],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.get(f"/api/campaigns/{campaign_id}/groups")
        data = response.json()
        assert data[0]["media_urls"] == ["img1.jpg", "img2.png"]


class TestLogsEdgeCases:
    async def test_logs_ordered_by_executed_at_desc(self, client, db_session):
        account = AccountFactory.create()
        db_session.add(account)
        await db_session.flush()

        campaign = CampaignFactory.create(account_id=account.id)
        db_session.add(campaign)
        await db_session.flush()

        group = GroupFactory.create(campaign_id=campaign.id)
        db_session.add(group)
        await db_session.flush()

        old = TaskLogFactory.create(
            group_id=group.id,
            status="SUCCESS",
            campaign_name="Old",
            executed_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
        new = TaskLogFactory.create(
            group_id=group.id,
            status="FAILED",
            campaign_name="New",
            executed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        db_session.add(old)
        db_session.add(new)
        await db_session.flush()

        response = await client.get("/api/logs/")
        data = response.json()
        assert data[0]["campaign_name"] == "New"
        assert data[1]["campaign_name"] == "Old"

    async def test_logs_contains_all_fields(self, client, db_session):
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
            campaign_name="Full Fields",
            status="FAILED",
            error_message="Connection timeout",
            retry_count=3,
        )
        db_session.add(log)
        await db_session.flush()

        response = await client.get("/api/logs/")
        data = response.json()[0]
        assert data["campaign_name"] == "Full Fields"
        assert data["error_message"] == "Connection timeout"
        assert data["retry_count"] == 3
        assert data["group_id"] == group.id
        assert "executed_at" in data


class TestCreateCampaignEmptyGroups:
    async def test_create_campaign_with_no_groups(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "No Groups",
                "account_id": account_id,
                "groups": [],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "No Groups"
        assert data["status"] == "SZKIC"
