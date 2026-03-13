from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    fb_email = Column(String, nullable=False)
    fb_password = Column(String, nullable=False)
    proxy_url = Column(String, nullable=True)
    session_file_path = Column(String, nullable=True)
    browser_profile_id = Column(String, nullable=True)
    session_cookies_backup = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaigns = relationship("Campaign", back_populates="account")
    fingerprint_tests = relationship("FingerprintTest", back_populates="account")


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"))

    base_interval_minutes = Column(Integer, default=840)
    random_deviation_percent = Column(Float, default=20.0)
    posts_per_day = Column(Integer, default=1)

    # Schedule windows
    active_hours_start = Column(String, default="08:00")  # HH:MM
    active_hours_end = Column(String, default="22:00")    # HH:MM
    active_days = Column(JSON, default=lambda: [0, 1, 2, 3, 4, 5, 6])  # 0=Mon, 6=Sun

    # SZKIC, AKTYWNA, WSTRZYMANA, ZAKOŃCZONA, BŁĄD
    status = Column(String, default="SZKIC")
    start_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="campaigns")
    groups = relationship("Group", back_populates="campaign")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    url = Column(String, nullable=False)
    name = Column(String, nullable=True)
    content = Column(String, nullable=False)
    media_urls = Column(JSON, nullable=True)
    background_style = Column(String, nullable=True)
    order = Column(Integer, default=0)
    planned_at = Column(DateTime(timezone=True), nullable=True)

    campaign = relationship("Campaign", back_populates="groups")
    task_logs = relationship("TaskLog", back_populates="group", cascade="all, delete-orphan")


class TaskLog(Base):
    __tablename__ = "task_logs"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"))

    campaign_name = Column(String, nullable=True)
    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    screenshot_path = Column(String, nullable=True)
    planned_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, default=0)

    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group", back_populates="task_logs")


class AppAuth(Base):
    __tablename__ = "app_auth"

    id = Column(Integer, primary_key=True, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FingerprintTest(Base):
    __tablename__ = "fingerprint_tests"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    status = Column(String, default="PENDING", nullable=False)
    proxy_url_used = Column(String, nullable=True)
    results = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    account = relationship("Account", back_populates="fingerprint_tests")
