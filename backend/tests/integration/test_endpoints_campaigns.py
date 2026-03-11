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
                "groups": ["https://fb.com/groups/1", "https://fb.com/groups/2"],
                "posts": ["Hello world", "Second post"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Campaign"
        assert data["status"] == "OCZEKUJE"
        assert data["account_id"] == account_id
        assert "id" in data

    async def test_create_campaign_default_values(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "Defaults",
                "account_id": account_id,
                "groups": ["url"],
                "posts": ["content"],
            },
        )
        data = response.json()
        assert data["base_interval_minutes"] == 60
        assert data["random_deviation_percent"] == 10.0

    async def test_create_campaign_custom_interval(self, client):
        account_id = await create_test_account(client)
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "Custom",
                "account_id": account_id,
                "groups": ["url"],
                "posts": ["content"],
                "base_interval_minutes": 30,
                "random_deviation_percent": 25.0,
            },
        )
        data = response.json()
        assert data["base_interval_minutes"] == 30
        assert data["random_deviation_percent"] == 25.0

    async def test_create_campaign_missing_name(self, client):
        response = await client.post(
            "/api/campaigns/",
            json={
                "account_id": 1,
                "groups": ["url"],
                "posts": ["content"],
            },
        )
        assert response.status_code == 422

    async def test_create_campaign_missing_groups(self, client):
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "No Groups",
                "account_id": 1,
                "posts": ["content"],
            },
        )
        assert response.status_code == 422

    async def test_create_campaign_missing_posts(self, client):
        response = await client.post(
            "/api/campaigns/",
            json={
                "name": "No Posts",
                "account_id": 1,
                "groups": ["url"],
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
                    "groups": ["url"],
                    "posts": ["content"],
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
                "groups": ["url"],
                "posts": ["content"],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/campaigns/{campaign_id}",
            json={"status": "W TOKU"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "W TOKU"

    async def test_update_campaign_status_all_transitions(self, client):
        account_id = await create_test_account(client)
        create_resp = await client.post(
            "/api/campaigns/",
            json={
                "name": "Transitions",
                "account_id": account_id,
                "groups": ["url"],
                "posts": ["content"],
            },
        )
        campaign_id = create_resp.json()["id"]

        for status in ["W TOKU", "ZATRZYMANE", "W TOKU", "OPUBLIKOWANE"]:
            response = await client.patch(
                f"/api/campaigns/{campaign_id}",
                json={"status": status},
            )
            assert response.status_code == 200
            assert response.json()["status"] == status

    async def test_update_campaign_not_found(self, client):
        response = await client.patch(
            "/api/campaigns/99999",
            json={"status": "W TOKU"},
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
                "groups": ["url"],
                "posts": ["content"],
            },
        )
        campaign_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/campaigns/{campaign_id}",
            json={},
        )
        assert response.status_code == 422
