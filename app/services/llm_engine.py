import json
import logging
import re
from typing import Dict, Any, Optional
import httpx

from app.config import settings
from app.models.schemas import (
    FeedbackCategory,
    SentimentType,
    LLMAnalysisOutput,
)

logger = logging.getLogger("signal2insight.llm")

EXTRACTION_SYSTEM_PROMPT = """You are an expert AI civic intelligence analyst for Signal2Insight.
Your mission is to analyze unstructured community feedback submitted by citizens (via text, hotline, or audio transcripts).
Extract and classify the feedback into a structured JSON object strictly matching this schema:

{
  "category": "Infrastructure" | "Public Health" | "Education" | "Safety" | "Governance" | "Environment",
  "sentiment": "Positive" | "Neutral" | "Negative",
  "urgency_score": <int from 1 to 5, where 1 is trivial/low and 5 is emergency danger>,
  "is_critical_alert": <boolean, MUST be true if urgency_score >= 4 or if immediate danger exists>,
  "summary": "<1-sentence clear summary of the core issue>",
  "recommended_action": "<concrete, prioritized actionable step for city officials>"
}

Rules:
1. "is_critical_alert" must be true whenever urgency_score is 4 or 5, or if there is active danger (e.g. gas leak, live wires, structural collapse, violence).
2. "summary" must be exactly 1 clear sentence summarizing the citizen's report.
3. Return ONLY valid JSON, with no surrounding markdown or explanation.
"""


def _mock_fallback_analyze(text: str) -> LLMAnalysisOutput:
    """
    Intelligent rule-based fallback analyzer when LLM API keys are absent or unavailable.
    Guarantees 100% uptime for hackathon demos while producing realistic, high-quality results.
    """
    lower = text.lower()

    # 1. Detect Category & Urgency heuristics
    # Extreme Safety hazards
    critical_safety_keywords = [
        "gas leak", "downed wire", "live wire", "power line", "explosion",
        "fire", "shooting", "armed", "collapse", "sinkhole", "danger",
        "emergency", "accident", "trapped", "hazardous"
    ]
    # Public health hazards
    critical_health_keywords = [
        "sewage", "contaminated water", "brown water", "toxic fumes",
        "chemical smell", "lead pipe", "mold", "epidemic", "food poisoning"
    ]
    # Standard infrastructure
    infra_keywords = [
        "pothole", "streetlight", "traffic light", "pavement", "sidewalk",
        "road", "water main", "leak", "bridge", "crosswalk", "speed bump",
        "culvert", "paving", "asphalt", "bus stop"
    ]
    # Education
    edu_keywords = [
        "school", "teacher", "classroom", "textbook", "student", "playground",
        "crossing guard", "after-school", "kindergarten", "library"
    ]
    # Environment
    env_keywords = [
        "trash", "dumping", "litter", "garbage", "tree", "branches",
        "air quality", "smog", "recycling", "park", "drainage", "pollution",
        "overgrown", "weeds"
    ]
    # Governance
    gov_keywords = [
        "permit", "taxes", "hearing", "city council", "voting", "election",
        "corruption", "transparency", "website", "clerk", "budget", "official"
    ]

    category = FeedbackCategory.GOVERNANCE
    urgency = 2

    if any(k in lower for k in critical_safety_keywords):
        category = FeedbackCategory.SAFETY
        urgency = 5
    elif any(k in lower for k in critical_health_keywords):
        category = FeedbackCategory.PUBLIC_HEALTH
        urgency = 4
    elif any(k in lower for k in infra_keywords):
        category = FeedbackCategory.INFRASTRUCTURE
        urgency = 3 if ("deep" in lower or "broken" in lower or "burst" in lower) else 2
    elif any(k in lower for k in edu_keywords):
        category = FeedbackCategory.EDUCATION
        urgency = 2
    elif any(k in lower for k in env_keywords):
        category = FeedbackCategory.ENVIRONMENT
        urgency = 2
    elif any(k in lower for k in gov_keywords):
        category = FeedbackCategory.GOVERNANCE
        urgency = 2

    # Boost urgency if explicit urgency indicators exist
    if any(k in lower for k in ["immediately", "urgent", "asap", "hazard", "threat", "severe", "crisis"]):
        urgency = min(5, urgency + 1)

    # 2. Detect Sentiment
    positive_keywords = [
        "thank", "thanks", "great", "excellent", "appreciate", "kudos",
        "wonderful", "love", "helpful", "good job", "fixed", "impressed"
    ]
    negative_keywords = [
        "terrible", "worst", "unacceptable", "furious", "angry", "disaster",
        "dangerous", "broken", "neglect", "useless", "hazard", "failed",
        "awful", "horrible", "ignoring", "complaint"
    ]

    pos_score = sum(1 for k in positive_keywords if k in lower)
    neg_score = sum(1 for k in negative_keywords if k in lower)

    if pos_score > neg_score and urgency <= 2:
        sentiment = SentimentType.POSITIVE
        urgency = 1
    elif neg_score > 0 or urgency >= 3:
        sentiment = SentimentType.NEGATIVE
    else:
        sentiment = SentimentType.NEUTRAL

    is_critical = urgency >= 4

    # 3. Formulate Summary
    cleaned_first_sentence = text.strip().split(".")[0].strip()
    if len(cleaned_first_sentence) > 120:
        cleaned_first_sentence = cleaned_first_sentence[:117] + "..."
    if sentiment == SentimentType.POSITIVE:
        summary = f"Citizen expresses gratitude regarding {category.value.lower()}: '{cleaned_first_sentence}'."
    else:
        summary = f"Citizen reports {category.value.lower()} concern: '{cleaned_first_sentence}'."

    # 4. Formulate Actionable Recommendation
    if sentiment == SentimentType.POSITIVE:
        recommended_action = "Acknowledge and log positive citizen feedback for municipal departmental commendation."
    else:
        recommendations_map = {
            FeedbackCategory.SAFETY: "Dispatch rapid response safety inspector and alert municipal emergency services.",
            FeedbackCategory.PUBLIC_HEALTH: "Alert Department of Public Health for on-site testing and containment.",
            FeedbackCategory.INFRASTRUCTURE: "Issue high-priority work order to Department of Public Works.",
            FeedbackCategory.ENVIRONMENT: "Schedule sanitation/parks crew for targeted clean-up and remediation.",
            FeedbackCategory.EDUCATION: "Forward inquiry to School District Liaison and Community Education Board.",
            FeedbackCategory.GOVERNANCE: "Route feedback to City Clerk's office for formal administrative review.",
        }
        recommended_action = recommendations_map.get(
            category, "Review feedback during next municipal administrative session."
        )

    if is_critical and category == FeedbackCategory.SAFETY:
        recommended_action = "CRITICAL: Deploy immediate hazard crew and cordon off surrounding perimeter."

    return LLMAnalysisOutput(
        category=category,
        sentiment=sentiment,
        urgency_score=urgency,
        is_critical_alert=is_critical,
        summary=summary,
        recommended_action=recommended_action,
    )


async def _call_openai(text: str, api_key: str) -> Optional[LLMAnalysisOutput]:
    """Call OpenAI API using structured JSON output format."""
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze this community feedback:\n\n{text}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        parsed = json.loads(raw_content)
        return LLMAnalysisOutput(**parsed)


async def _call_gemini(text: str, api_key: str) -> Optional[LLMAnalysisOutput]:
    """Call Google Gemini API with JSON output mode."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{EXTRACTION_SYSTEM_PROMPT}\n\nCommunity Feedback to analyze:\n{text}"}
                ]
            }
        ],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.1,
        }
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        candidate = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(candidate)
        return LLMAnalysisOutput(**parsed)


async def analyze_feedback_text(text: str) -> LLMAnalysisOutput:
    """
    Main asynchronous analysis function.
    Tries configured LLM provider, with robust fallback to smart mock engine on any failure.
    """
    openai_key = settings.openai_api_key
    gemini_key = settings.gemini_api_key

    # Try OpenAI if configured
    if openai_key and settings.llm_provider in ("openai", "auto"):
        try:
            result = await _call_openai(text, openai_key)
            if result:
                return result
        except Exception as e:
            logger.warning(f"OpenAI LLM extraction failed: {e}. Falling back...")

    # Try Gemini if configured
    if gemini_key and settings.llm_provider in ("gemini", "auto"):
        try:
            result = await _call_gemini(text, gemini_key)
            if result:
                return result
        except Exception as e:
            logger.warning(f"Gemini LLM extraction failed: {e}. Falling back...")

    # Smart, deterministic heuristic mock fallback
    logger.info("Using intelligent heuristic mock engine for feedback analysis.")
    return _mock_fallback_analyze(text)
