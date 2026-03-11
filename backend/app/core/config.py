from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "SOSM API"
    VERSION: str = "1.0.0"
    
    # PostgreSQL configuration
    POSTGRES_USER: str = "sosm_user"
    POSTGRES_PASSWORD: str = "sosm_password"
    POSTGRES_DB: str = "sosm_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """For Alembic (sync driver)"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: str = "6379"

    # Donut Browser Local API (enable in Settings, copy Bearer token)
    DONUT_API_URL: str = "http://127.0.0.1:10108"
    DONUT_API_TOKEN: str = ""
    FINGERPRINT_PROFILE_ID: str = ""
    BROWSER_CONCURRENCY: int = 10
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    class Config:
        env_file = ".env"

settings = Settings()
