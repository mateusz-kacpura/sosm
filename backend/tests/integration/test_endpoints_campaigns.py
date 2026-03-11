import pytest


async def create_test_account(client):
    resp = await client.post(
        "/api/accounts/",
        json={"fb_email": "campaign_test@fb.com", "fb_password": "pass"},
    )
    return resp.json()["id"]


class TestCreateCampaign:
    async def test_create_campaign_success(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "My Campaign",
                "account_id": account_id,
                "groups": [
                    {"url": "https://fb.com/groups/1", "content": "Hello world"},
                    {"url": "https://fb.com/groups/2", "content": "Second post"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Campaign"
        assert data["status"] == "SZKIC"
        assert data["account_id"] == account_id
        assert "id" in data

    async def test_create_campaign_default_values(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "Defaults",
                "account_id": account_id,
                "groups": [{"url": "url", "content": "content"}],
            },
        )
        data = response.json()
        assert data["base_interval_minutes"] == 60
        assert data["random_deviation_percent"] == 10.0
        assert data["start_at"] is None

    async def test_create_campaign_custom_interval(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "Custom",
                "account_id": account_id,
                "groups": [{"url": "url", "content": "content"}],
                "base_interval_minutes": 30,
                "random_deviation_percent": 25.0,
            },
        )
        data = response.json()
        assert data["base_interval_minutes"] == 30
        assert data["random_deviation_percent"] == 25.0

    async def test_create_campaign_with_start_at(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "Scheduled",
                "account_id": account_id,
                "groups": [{"url": "url", "content": "content"}],
                "start_at": "2026-06-01T12:00:00Z",
            },
        )
        data = response.json()
        assert data["start_at"] is not None

    async def test_create_campaign_missing_name(self, client):
        response = await client.post(
            "/api/campaigns/",
            json={
                "account_id": 1,
                "groups": [{"url": "url", "content": "c"}],
            },
        )
        assert response.status_code == 422

    async def test_create_campaign_missing_groups(self, client):
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "No Groups",
                "account_id": 1,
            },
        )
        assert response.status_code == 422


class TestListCampaigns:
    async def test_list_campaigns_empty(self, client):
        response = await client.get("/api/campaigns/")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_campaigns_returns_all(self, client):
        account_id = await create_test_account(client)
        for i in range(3):
            await client.post(
                "/api/campaigns/",
                json={
                    "name": f"Campaign {i}",
                    "account_id": account_id,
                    "groups": [{"url": "url", "content": "content"}],
                },
            )

        response = await client.get("/api/campaigns/")
        assert len(response.json()) == 3


class TestUpdateCampaignStatus:
    async def test_update_campaign_status_success(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "To Update",
                "account_id": account_id,
                "groups": [{"url": "url", "content": "content"}],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/campaigns/{campaign_id}",
            json={"status": "AKTYWNA"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "AKTYWNA"

    async def test_update_campaign_status_all_transitions(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "Transitions",
                "account_id": account_id,
                "groups": [{"url": "url", "content": "content"}],
            },
        )
        campaign_id = create_resp.json()["id"]

        for status in ["AKTYWNA", "WSTRZYMANA", "AKTYWNA", "ZAKOŃCZONA"]:
            response = await client.patch(
                f"/api/campaigns/{campaign_id}",
                json={"status": status},
            )
            assert response.status_code == 200
            assert response.json()["status"] == status

    async def test_update_campaign_not_found(self, client):
        response = await client.patch(
            "/api/campaigns/99999",
            json={"status": "AKTYWNA"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Campaign not found"

    async def test_update_campaign_missing_status(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "No Status",
                "account_id": account_id,
                "groups": [{"url": "url", "content": "content"}],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/campaigns/{campaign_id}",
            json={},
        )
        assert response.status_code == 422


class TestGetCampaignGroups:
    async def test_get_campaign_groups_success(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "Groups Test",
                "account_id": account_id,
                "groups": [
                    {"url": "https://fb.com/groups/1", "content": "Content 1"},
                    {"url": "https://fb.com/groups/2", "content": "Content 2"},
                    {"url": "https://fb.com/groups/3", "content": "Content 3"},
                ],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.get(f"/api/campaigns/{campaign_id}/groups")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("content" in g for g in data)
        assert data[0]["order"] == 0
        assert data[2]["order"] == 2

    async def test_get_campaign_groups_empty(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "Empty",
                "account_id": account_id,
                "groups": [],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.get(f"/api/campaigns/{campaign_id}/groups")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_campaign_groups_nonexistent(self, client):
        response = await client.get("/api/campaigns/99999/groups")
        assert response.status_code == 200
        assert response.json() == []
