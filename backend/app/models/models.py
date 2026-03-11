from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    accounts = relationship("Account", back_populates="owner")

class Account(Base):
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    fb_email = Column(String, nullable=False)
    fb_password = Column(String, nullable=False)
    proxy_url = Column(String, nullable=True)
    # Ścieżka do zapisanego stanu sesji przeglądarki (np. storage_state.json)
    session_file_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    owner = relationship("User", back_populates="accounts")
    campaigns = relationship("Campaign", back_populates="account")

class Campaign(Base):
    __tablename__ = "campaigns"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    
    # Interwał pomiędzy postami w minutach np. 60
    base_interval_minutes = Column(Integer, default=60)
    # Odchylenie losowe (np. 10% z 60 minut = +/- 6 minut)
    random_deviation_percent = Column(Float, default=10.0)
    
    # OCZEKUJE, W TOKU, OPUBLIKOWANE, ZATRZYMANE
    status = Column(String, default="OCZEKUJE")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    account = relationship("Account", back_populates="campaigns")
    posts = relationship("Post", back_populates="campaign")
    groups = relationship("Group", back_populates="campaign")

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    url = Column(String, nullable=False)
    name = Column(String, nullable=True) # opcjonalnie nazwa pobrana przy pierwszym wejściu
    
    campaign = relationship("Campaign", back_populates="groups")

class Post(Base):
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"))
    content = Column(String, nullable=False)
    media_urls = Column(JSON, nullable=True) # lista ścieżek/URLi do zdjęć
    
    campaign = relationship("Campaign", back_populates="posts")
    tasks = relationship("TaskLog", back_populates="post")

class TaskLog(Base):
    __tablename__ = "task_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"))
    group_url = Column(String, nullable=False) # konkretna grupa gdzie był rzucany post
    
    # STATUS: SUCCESS, FAILED, CHECKPOINT_DETECTED
    status = Column(String, nullable=False)
    error_message = Column(String, nullable=True)
    screenshot_path = Column(String, nullable=True) # jeśli wykryto checkpoint
    
    executed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    post = relationship("Post", back_populates="tasks")
