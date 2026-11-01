from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, field_validator


class FeedbackCategory(str, Enum):
    INFRASTRUCTURE = "Infrastructure"
    PUBLIC_HEALTH = "Public Health"
    EDUCATION = "Education"
    SAFETY = "Safety"
    GOVERNANCE = "Governance"
    ENVIRONMENT = "Environment"


class SentimentType(str, Enum):
    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"


class LLMAnalysisOutput(BaseModel):
    """Structured output expected directly from the LLM extraction step."""
    category: FeedbackCategory = Field(
        ...,
        description="The civic domain category best describing the community issue."
    )
    sentiment: SentimentType = Field(
        ...,
        description="Sentiment assessment of the feedback: Positive, Neutral, or Negative."
    )
    urgency_score: int = Field(
        ...,
        ge=1,
        le=5,
        description="Integer score from 1 (lowest urgency) to 5 (immediate emergency)."
    )
    is_critical_alert: bool = Field(
        ...,
        description="Flag whether this issue requires immediate municipal/emergency response."
    )
    summary: str = Field(
        ...,
        description="A clear 1-sentence executive summary of the feedback."
    )
    recommended_action: str = Field(
        ...,
        description="A specific, actionable next step recommendation for community officials."
    )

    @field_validator("is_critical_alert", mode="after")
    @classmethod
    def enforce_critical_threshold(cls, v: bool, info) -> bool:
        """Enforces critical alert flag whenever urgency is 4 or 5."""
        urgency = info.data.get("urgency_score", 1)
        if urgency >= 4:
            return True
        return v


class FeedbackEntry(BaseModel):
    """Canonical model for a processed citizen feedback record."""
    entry_id: str = Field(
        default_factory=lambda: f"fb_{uuid4().hex[:8]}",
        description="Unique identifier for the feedback entry."
    )
    raw_text: str = Field(
        ...,
        description="Original verbatim community feedback text or audio transcription."
    )
    source: str = Field(
        default="text",
        description="Ingestion channel: 'text', 'audio', 'web_form', or 'sms'."
    )
    location: Optional[str] = Field(
        default=None,
        description="Neighborhood, district, or GPS reference if available."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the entry was received and processed."
    )
    category: FeedbackCategory = Field(
        ...,
        description="Civic category: Infrastructure, Public Health, Education, Safety, Governance, Environment."
    )
    sentiment: SentimentType = Field(
        ...,
        description="Sentiment: Positive, Neutral, or Negative."
    )
    urgency_score: int = Field(
        ...,
        ge=1,
        le=5,
        description="Urgency score from 1 (low) to 5 (critical)."
    )
    is_critical_alert: bool = Field(
        ...,
        description="True if urgency >= 4 or involves immediate public danger."
    )
    summary: str = Field(
        ...,
        description="1-sentence summary of the report."
    )
    recommended_action: str = Field(
        ...,
        description="Suggested step for community officials."
    )

    @field_validator("is_critical_alert", mode="after")
    @classmethod
    def validate_critical_status(cls, v: bool, info) -> bool:
        """Guarantee critical flag is True if urgency >= 4."""
        urgency = info.data.get("urgency_score", 1)
        if urgency >= 4:
            return True
        return v


class FeedbackIngestionRequest(BaseModel):
    """Payload for submitting single raw feedback."""
    text: str = Field(..., min_length=3, description="Verbatim citizen feedback string")
    source: Optional[str] = Field("text", description="Channel of receipt")
    location: Optional[str] = Field(None, description="Reported location/district")


class BatchIngestionRequest(BaseModel):
    """Payload for batch processing multiple feedback items."""
    entries: List[FeedbackIngestionRequest]


class BatchIngestionResponse(BaseModel):
    """Response returned after processing a batch."""
    processed_count: int
    critical_alerts_count: int
    entries: List[FeedbackEntry]


class AnalyticsOverview(BaseModel):
    """High-level metrics for dashboard visualization."""
    total_entries: int
    critical_alerts_count: int
    average_urgency: float
    category_distribution: Dict[str, int]
    sentiment_distribution: Dict[str, int]
    urgency_distribution: Dict[int, int]
    recent_critical_alerts: List[FeedbackEntry]
