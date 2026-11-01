"""API Routes package."""
from app.routes.feedback import router as feedback_router
from app.routes.analytics import router as analytics_router

__all__ = ["feedback_router", "analytics_router"]
