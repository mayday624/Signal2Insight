import asyncio
import logging
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status

from app.models.schemas import (
    BatchIngestionRequest,
    BatchIngestionResponse,
    FeedbackCategory,
    FeedbackEntry,
    FeedbackIngestionRequest,
    SentimentType,
)
from app.services.audio_service import transcribe_audio_file
from app.services.llm_engine import analyze_feedback_text
from app.storage.repository import repository

logger = logging.getLogger("signal2insight.routes.feedback")
router = APIRouter(prefix="/api/feedback", tags=["Feedback Ingestion & Management"])


@router.post(
    "/ingest",
    response_model=FeedbackEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest and analyze raw community text feedback",
)
async def ingest_feedback(payload: FeedbackIngestionRequest):
    """
    Ingest a single text feedback entry.
    Asynchronously passes text through the structured LLM extraction pipeline
    and persists the validated Pydantic FeedbackEntry.
    """
    try:
        # Run async structured LLM analysis
        analysis = await analyze_feedback_text(payload.text)

        entry = FeedbackEntry(
            entry_id=f"fb_{uuid4().hex[:8]}",
            raw_text=payload.text,
            source=payload.source or "text",
            location=payload.location,
            category=analysis.category,
            sentiment=analysis.sentiment,
            urgency_score=analysis.urgency_score,
            is_critical_alert=analysis.is_critical_alert,
            summary=analysis.summary,
            recommended_action=analysis.recommended_action,
        )

        saved = repository.add_entry(entry)
        return saved
    except Exception as e:
        logger.error(f"Error processing feedback ingestion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process feedback entry: {str(e)}",
        )


@router.post(
    "/ingest-audio",
    response_model=FeedbackEntry,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest civic audio recording or voicemail",
)
async def ingest_audio_feedback(
    file: UploadFile = File(..., description="Audio file (.wav, .mp3, .m4a, etc.)"),
    location: Optional[str] = Form(None, description="Optional reported neighborhood/location"),
):
    """
    Accepts an audio file upload, transcribes it via Whisper or mock engine,
    and runs it through the full structured LLM analysis pipeline.
    """
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio file provided.",
            )

        transcribed_text = await transcribe_audio_file(
            file_bytes=audio_bytes,
            filename=file.filename or "recording.wav",
            content_type=file.content_type or "audio/wav",
        )

        analysis = await analyze_feedback_text(transcribed_text)

        entry = FeedbackEntry(
            entry_id=f"fb_aud_{uuid4().hex[:6]}",
            raw_text=transcribed_text,
            source="audio",
            location=location,
            category=analysis.category,
            sentiment=analysis.sentiment,
            urgency_score=analysis.urgency_score,
            is_critical_alert=analysis.is_critical_alert,
            summary=analysis.summary,
            recommended_action=analysis.recommended_action,
        )

        saved = repository.add_entry(entry)
        return saved
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process audio feedback: {str(e)}",
        )


@router.post(
    "/batch",
    response_model=BatchIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch ingest multiple community feedback entries concurrently",
)
async def batch_ingest_feedback(batch: BatchIngestionRequest):
    """
    Process multiple citizen feedback submissions concurrently using asyncio.gather.
    """
    async def process_single(item: FeedbackIngestionRequest) -> FeedbackEntry:
        analysis = await analyze_feedback_text(item.text)
        entry = FeedbackEntry(
            entry_id=f"fb_{uuid4().hex[:8]}",
            raw_text=item.text,
            source=item.source or "batch",
            location=item.location,
            category=analysis.category,
            sentiment=analysis.sentiment,
            urgency_score=analysis.urgency_score,
            is_critical_alert=analysis.is_critical_alert,
            summary=analysis.summary,
            recommended_action=analysis.recommended_action,
        )
        return repository.add_entry(entry)

    # Process all concurrently
    processed_entries = await asyncio.gather(
        *(process_single(item) for item in batch.entries),
        return_exceptions=False,
    )

    critical_count = sum(1 for e in processed_entries if e.is_critical_alert)

    return BatchIngestionResponse(
        processed_count=len(processed_entries),
        critical_alerts_count=critical_count,
        entries=processed_entries,
    )


@router.get(
    "",
    response_model=List[FeedbackEntry],
    summary="Query and filter community feedback entries",
)
def list_feedback(
    category: Optional[FeedbackCategory] = Query(None, description="Filter by civic category"),
    sentiment: Optional[SentimentType] = Query(None, description="Filter by sentiment"),
    is_critical_alert: Optional[bool] = Query(None, description="Filter for critical alerts only"),
    min_urgency: Optional[int] = Query(None, ge=1, le=5, description="Minimum urgency rating"),
    max_urgency: Optional[int] = Query(None, ge=1, le=5, description="Maximum urgency rating"),
    search: Optional[str] = Query(None, description="Search keyword in text, summary, or action"),
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Offset pagination index"),
):
    """List and filter all community feedback entries."""
    return repository.list_entries(
        category=category,
        sentiment=sentiment,
        is_critical_alert=is_critical_alert,
        min_urgency=min_urgency,
        max_urgency=max_urgency,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{entry_id}",
    response_model=FeedbackEntry,
    summary="Get single feedback entry details",
)
def get_feedback(entry_id: str):
    """Retrieve details for a specific feedback entry."""
    entry = repository.get_entry(entry_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback entry '{entry_id}' not found.",
        )
    return entry


@router.delete(
    "/{entry_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a feedback entry",
)
def delete_feedback(entry_id: str):
    """Remove a feedback record from the system."""
    deleted = repository.delete_entry(entry_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feedback entry '{entry_id}' not found.",
        )
    return {"status": "success", "message": f"Entry {entry_id} deleted."}


@router.post(
    "/clear",
    summary="Clear all feedback records",
)
def clear_all_feedback():
    """Wipes all feedback records from the database."""
    repository.clear_all()
    return {"status": "success", "message": "All feedback records cleared."}
