"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import admin, auth, gallery, health, images, videos

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(images.router, prefix="/images", tags=["images"])
api_router.include_router(videos.router, prefix="/videos", tags=["videos"])
api_router.include_router(gallery.router, prefix="/gallery", tags=["gallery"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(health.router, prefix="/health", tags=["health"])

__all__ = ["api_router"]
