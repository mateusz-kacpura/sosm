from app.core.config import Settings


class TestSettings:
    def test_database_url_construction(self):
        s = Settings(
            POSTGRES_USER="user",
            POSTGRES_PASSWORD="pass",
            POSTGRES_HOST="myhost",
            POSTGRES_PORT="5433",
            POSTGRES_DB="mydb",
        )
        assert s.DATABASE_URL == "postgresql+asyncpg://user:pass@myhost:5433/mydb"

    def test_database_url_sync_construction(self):
        s = Settings(
            POSTGRES_USER="user",
            POSTGRES_PASSWORD="pass",
            POSTGRES_HOST="myhost",
            POSTGRES_PORT="5433",
            POSTGRES_DB="mydb",
        )
        assert s.DATABASE_URL_SYNC == "postgresql://user:pass@myhost:5433/mydb"

    def test_redis_url_construction(self):
        s = Settings(REDIS_HOST="redis-host", REDIS_PORT="6380")
        assert s.REDIS_URL == "redis://redis-host:6380/0"

    def test_default_values(self):
        s = Settings()
        assert s.PROJECT_NAME == "SOSM API"
        assert s.VERSION == "1.0.0"
        assert s.POSTGRES_USER == "sosm_user"
        assert s.POSTGRES_PASSWORD == "sosm_password"
        assert s.POSTGRES_DB == "sosm_db"
        assert s.POSTGRES_HOST == "localhost"
        assert s.POSTGRES_PORT == "5432"
        assert s.REDIS_HOST == "localhost"
        assert s.REDIS_PORT == "6379"
