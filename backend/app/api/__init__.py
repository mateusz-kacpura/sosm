from fastapi import APIRouter

api_router = APIRouter()

# Tutaj zdefiniujemy i zaimportujemy kolejne routery:
# api_router.include_router(users.router, prefix="/users", tags=["users"])
# api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"])
