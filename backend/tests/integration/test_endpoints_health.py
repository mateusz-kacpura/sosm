class TestHealthCheck:
    async def test_health_check(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"


class TestStartupEvent:
    async def test_startup_event_runs(self):
        from app.main import startup_event
        # Should not raise - just logs a message
        await startup_event()


class TestGetDb:
    async def test_get_db_yields_session(self):
        from unittest.mock import AsyncMock, MagicMock, patch
        from contextlib import asynccontextmanager

        mock_session = AsyncMock()

        @asynccontextmanager
        async def mock_session_factory():
            yield mock_session

        with patch("app.core.database.AsyncSessionLocal", mock_session_factory):
            from app.core.database import get_db
            gen = get_db()
            session = await gen.__anext__()
            assert session is mock_session
            try:
                await gen.__anext__()
            except StopAsyncIteration:
                pass
