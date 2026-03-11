import pytest


async def create_campaign_with_posts(client, posts_count=3):
    acc_resp = await client.post(
        "/api/accounts/",
        json={"fb_email": "posts_test@fb.com", "fb_password": "pass"},
    )
    account_id = acc_resp.json()["id"]

    posts = [f"Post content {i}" for i in range(posts_count)]
    camp_resp = await client.post(
        "/api/campaigns/",
        json={
            "name": "Posts Campaign",
            "account_id": account_id,
            "groups": ["https://fb.com/groups/1"],
            "posts": posts,
        },
    )
    return camp_resp.json()["id"]


class TestGetCampaignPosts:
    async def test_get_campaign_posts_success(self, client):
        campaign_id = await create_campaign_with_posts(client, posts_count=3)

        response = await client.get(f"/api/campaigns/{campaign_id}/posts")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert all("content" in post for post in data)

    async def test_get_campaign_posts_empty(self, client):
        campaign_id = await create_campaign_with_posts(client, posts_count=0)

        response = await client.get(f"/api/campaigns/{campaign_id}/posts")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_campaign_posts_nonexistent_campaign(self, client):
        response = await client.get("/api/campaigns/99999/posts")
        assert response.status_code == 200
        assert response.json() == []
