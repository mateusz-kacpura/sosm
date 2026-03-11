from app.core.database import Base
from .models import User, Account, Campaign, Group, Post, TaskLog

# Udostępniamy modele dla autogeneracji w Alembic
__all__ = ["Base", "User", "Account", "Campaign", "Group", "Post", "TaskLog"]
