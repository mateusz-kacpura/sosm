import os
import sys
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "SOSM API"
    VERSION: str = "1.0.0"

    # Standalone mode: SQLite + in-process tasks (no Docker/Redis/Celery)
    STANDALONE: bool = False

    # PostgreSQL configuration (Docker mode)
    POSTGRES_USER: str = "sosm_user"
    POSTGRES_PASSWORD: str = "sosm_password"
    POSTGRES_DB: str = "sosm_db"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    # Redis configuration (Docker mode)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: str = "6379"

    # Donut Browser Local API (used by system management UI only)
    DONUT_API_URL: str = "http://127.0.0.1:10108"
    DONUT_API_TOKEN: str = ""
    FINGERPRINT_ACCOUNT_ID: int = 0  # account ID for fingerprint tests (0 = use request.account_id)
    BROWSER_CONCURRENCY: int = 10
    MEDIA_UPLOAD_DIR: str = ""

    # Donut Browser data directory (profiles, binaries)
    DONUT_DATA_DIR: str = ""  # default: ~/.local/share/DonutBrowser
    CAMOUFOX_HEADLESS: str = "virtual"  # "virtual" (Xvfb), "true", "false"

    @property
    def MEDIA_DIR(self) -> str:
        if self.MEDIA_UPLOAD_DIR:
            return self.MEDIA_UPLOAD_DIR
        return os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'media_uploads'))

    @property
    def DATA_DIR(self) -> str:
        if self.STANDALONE:
            if getattr(sys, 'frozen', False):
                # Running as PyInstaller binary
                if sys.platform == 'win32':
                    base = os.environ.get('APPDATA', os.path.expanduser('~'))
                else:
                    base = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
                return os.path.join(base, 'SOSM')
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'sosm_data')
        return "."

    @property
    def DATABASE_URL(self) -> str:
        if self.STANDALONE:
            # In standalone+Docker hybrid, use PostgreSQL if POSTGRES_HOST is configured
            if os.environ.get("POSTGRES_HOST"):
                return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            db_path = os.path.join(self.DATA_DIR, "sosm.db")
            return f"sqlite+aiosqlite:///{db_path}"
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        """For Alembic (sync driver)"""
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    class Config:
        env_file = ".env"

settings = Settings()
