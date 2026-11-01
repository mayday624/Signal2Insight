from typing import Dict, List
from fastapi import APIRouter
from app.models.schemas import AnalyticsOverview, FeedbackEntry
from app.storage.repository import repository

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Insights"])


@router.get(
    "/overview",
    response_model=AnalyticsOverview,
    summary="Get aggregated civic engagement metrics and distributions",
)
def get_analytics_overview():
    """Returns high-level statistics, alert counts, and distribution metrics."""
    return repository.get_analytics()


@router.get(
    "/critical-alerts",
    response_model=List[FeedbackEntry],
    summary="List all current critical safety & hazard alerts",
)
def get_critical_alerts():
    """Retrieve only entries flagged as critical emergencies (urgency >= 4)."""
    return repository.list_entries(is_critical_alert=True)


@router.get(
    "/breakdown",
    summary="Cross-tabulation of category vs sentiment",
)
def get_category_sentiment_breakdown() -> Dict[str, Dict[str, int]]:
    """Returns matrix of feedback counts grouped by category and sentiment."""
    entries = repository.list_entries(limit=1000)
    matrix: Dict[str, Dict[str, int]] = {}

    for e in entries:
        cat = e.category.value
        sent = e.sentiment.value
        if cat not in matrix:
            matrix[cat] = {"Positive": 0, "Neutral": 0, "Negative": 0}
        matrix[cat][sent] = matrix[cat].get(sent, 0) + 1

    return matrix
