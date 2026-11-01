import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import FeedbackCategory, SentimentType, FeedbackEntry, LLMAnalysisOutput
from app.services.llm_engine import analyze_feedback_text, _mock_fallback_analyze
from app.storage.repository import FeedbackRepository

client = TestClient(app)


def test_schema_critical_alert_enforcement():
    """Ensure Pydantic validator automatically sets is_critical_alert=True if urgency >= 4."""
    # When urgency is 4, even if False was passed, it becomes True
    output = LLMAnalysisOutput(
        category=FeedbackCategory.SAFETY,
        sentiment=SentimentType.NEGATIVE,
        urgency_score=4,
        is_critical_alert=False,
        summary="Test critical scenario",
        recommended_action="Dispatch safety team"
    )
    assert output.is_critical_alert is True
    assert output.urgency_score == 4


def test_llm_engine_fallback_hazard_detection():
    """Verify that dangerous keywords flag emergency safety issues."""
    text = "EMERGENCY: Natural gas leak sparking near underground pipe in commercial alleyway!"
    analysis = _mock_fallback_analyze(text)

    assert analysis.category == FeedbackCategory.SAFETY
    assert analysis.urgency_score == 5
    assert analysis.is_critical_alert is True
    assert "hazard" in analysis.recommended_action.lower() or "emergency" in analysis.recommended_action.lower()


def test_llm_engine_fallback_water_health_hazard():
    """Verify public health water hazard is flagged critical."""
    text = "Brown contaminated water flowing into sinks with severe odor and children sick."
    analysis = _mock_fallback_analyze(text)

    assert analysis.category == FeedbackCategory.PUBLIC_HEALTH
    assert analysis.urgency_score >= 4
    assert analysis.is_critical_alert is True


def test_llm_engine_positive_feedback():
    """Verify positive community gratitude sentiment."""
    text = "Thank you so much to the parks division for the wonderful new solar recycling bins!"
    analysis = _mock_fallback_analyze(text)

    assert analysis.sentiment == SentimentType.POSITIVE
    assert analysis.urgency_score == 1
    assert analysis.is_critical_alert is False


def test_api_health_endpoint():
    """Check /health status endpoint."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "total_records" in data


def test_api_ingest_and_analytics_flow():
    """Test full cycle: ingest text via API, verify Pydantic structure and analytics update."""
    payload = {
        "text": "Huge sinkhole opened up in front of the community center, cars are swerving into oncoming traffic!",
        "source": "web_form",
        "location": "Central Boulevard"
    }
    res = client.post("/api/feedback/ingest", json=payload)
    assert res.status_code == 201
    entry = res.json()

    assert entry["category"] in ["Safety", "Infrastructure"]
    assert entry["urgency_score"] >= 4
    assert entry["is_critical_alert"] is True
    assert entry["location"] == "Central Boulevard"
    assert "summary" in entry
    assert "recommended_action" in entry

    # Verify presence in list query
    list_res = client.get("/api/feedback?is_critical_alert=true")
    assert list_res.status_code == 200
    critical_entries = list_res.json()
    assert any(e["entry_id"] == entry["entry_id"] for e in critical_entries)

    # Verify analytics overview reflects it
    analytics_res = client.get("/api/analytics/overview")
    assert analytics_res.status_code == 200
    overview = analytics_res.json()
    assert overview["critical_alerts_count"] >= 1
    assert overview["total_entries"] >= 1


def test_web_dashboard_html_render():
    """Ensure standalone HTML web dashboard renders valid HTML page."""
    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "Signal2Insight" in res.text
    assert "<canvas id=\"categoryChart\"" in res.text
