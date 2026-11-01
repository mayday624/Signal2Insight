import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import threading

from app.config import settings
from app.models.schemas import (
    FeedbackCategory,
    SentimentType,
    FeedbackEntry,
    AnalyticsOverview,
)

logger = logging.getLogger("signal2insight.storage")


class FeedbackRepository:
    """Thread-safe persistent repository backed by SQLite with in-memory caching."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.sqlite_db_path
        self._lock = threading.Lock()
        self._cache: Dict[str, FeedbackEntry] = {}
        self._init_db()
        self._load_from_db()

        if not self._cache and settings.enable_seed_data:
            self.load_seed_data()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes SQLite tables."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS feedback_entries (
                    entry_id TEXT PRIMARY KEY,
                    raw_text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    location TEXT,
                    created_at TEXT NOT NULL,
                    category TEXT NOT NULL,
                    sentiment TEXT NOT NULL,
                    urgency_score INTEGER NOT NULL,
                    is_critical_alert INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    recommended_action TEXT NOT NULL
                )
            """)
            conn.commit()

    def _load_from_db(self):
        """Populates the in-memory cache from the SQLite database."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM feedback_entries ORDER BY created_at DESC")
            rows = cursor.fetchall()
            for r in rows:
                entry = FeedbackEntry(
                    entry_id=r["entry_id"],
                    raw_text=r["raw_text"],
                    source=r["source"],
                    location=r["location"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    category=FeedbackCategory(r["category"]),
                    sentiment=SentimentType(r["sentiment"]),
                    urgency_score=r["urgency_score"],
                    is_critical_alert=bool(r["is_critical_alert"]),
                    summary=r["summary"],
                    recommended_action=r["recommended_action"],
                )
                self._cache[entry.entry_id] = entry

    def load_seed_data(self):
        """Loads default civic seed records from data/seed_data.json."""
        seed_path = Path("data/seed_data.json")
        if not seed_path.exists():
            # Check relative to project root
            seed_path = Path(__file__).resolve().parent.parent.parent / "data" / "seed_data.json"

        if seed_path.exists():
            try:
                with open(seed_path, "r", encoding="utf-8") as f:
                    items = json.load(f)
                    for item in items:
                        entry = FeedbackEntry(**item)
                        self.add_entry(entry)
                logger.info(f"Loaded {len(items)} seed entries successfully.")
            except Exception as e:
                logger.error(f"Failed to load seed data: {e}")

    def add_entry(self, entry: FeedbackEntry) -> FeedbackEntry:
        """Stores a feedback entry in memory and SQLite."""
        with self._lock:
            self._cache[entry.entry_id] = entry
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO feedback_entries (
                        entry_id, raw_text, source, location, created_at,
                        category, sentiment, urgency_score, is_critical_alert,
                        summary, recommended_action
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.raw_text,
                        entry.source,
                        entry.location,
                        entry.created_at.isoformat(),
                        entry.category.value,
                        entry.sentiment.value,
                        entry.urgency_score,
                        1 if entry.is_critical_alert else 0,
                        entry.summary,
                        entry.recommended_action,
                    ),
                )
                conn.commit()
        return entry

    def get_entry(self, entry_id: str) -> Optional[FeedbackEntry]:
        """Retrieves a single feedback entry by its ID."""
        with self._lock:
            return self._cache.get(entry_id)

    def delete_entry(self, entry_id: str) -> bool:
        """Deletes a feedback entry by ID."""
        with self._lock:
            if entry_id in self._cache:
                del self._cache[entry_id]
                with self._get_connection() as conn:
                    conn.execute("DELETE FROM feedback_entries WHERE entry_id = ?", (entry_id,))
                    conn.commit()
                return True
            return False

    def list_entries(
        self,
        category: Optional[FeedbackCategory] = None,
        sentiment: Optional[SentimentType] = None,
        is_critical_alert: Optional[bool] = None,
        min_urgency: Optional[int] = None,
        max_urgency: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[FeedbackEntry]:
        """Filters and returns a list of feedback entries."""
        with self._lock:
            entries = list(self._cache.values())

        # Sort descending by creation date
        entries.sort(key=lambda x: x.created_at, reverse=True)

        filtered = []
        for e in entries:
            if category and e.category != category:
                continue
            if sentiment and e.sentiment != sentiment:
                continue
            if is_critical_alert is not None and e.is_critical_alert != is_critical_alert:
                continue
            if min_urgency is not None and e.urgency_score < min_urgency:
                continue
            if max_urgency is not None and e.urgency_score > max_urgency:
                continue
            if search:
                query = search.lower()
                matched = (
                    query in e.raw_text.lower()
                    or query in e.summary.lower()
                    or query in e.recommended_action.lower()
                    or (e.location and query in e.location.lower())
                )
                if not matched:
                    continue
            filtered.append(e)

        return filtered[offset : offset + limit]

    def get_analytics(self) -> AnalyticsOverview:
        """Calculates aggregated metrics for dashboards."""
        with self._lock:
            entries = list(self._cache.values())

        total = len(entries)
        if total == 0:
            return AnalyticsOverview(
                total_entries=0,
                critical_alerts_count=0,
                average_urgency=0.0,
                category_distribution={c.value: 0 for c in FeedbackCategory},
                sentiment_distribution={s.value: 0 for s in SentimentType},
                urgency_distribution={i: 0 for i in range(1, 6)},
                recent_critical_alerts=[],
            )

        critical_count = sum(1 for e in entries if e.is_critical_alert)
        avg_urgency = round(sum(e.urgency_score for e in entries) / total, 2)

        # Category counts
        cat_dist = {c.value: 0 for c in FeedbackCategory}
        for e in entries:
            cat_dist[e.category.value] = cat_dist.get(e.category.value, 0) + 1

        # Sentiment counts
        sent_dist = {s.value: 0 for s in SentimentType}
        for e in entries:
            sent_dist[e.sentiment.value] = sent_dist.get(e.sentiment.value, 0) + 1

        # Urgency counts
        urg_dist = {i: 0 for i in range(1, 6)}
        for e in entries:
            urg_dist[e.urgency_score] = urg_dist.get(e.urgency_score, 0) + 1

        # Recent critical alerts sorted by urgency desc, then date desc
        critical_alerts = [e for e in entries if e.is_critical_alert]
        critical_alerts.sort(key=lambda x: (x.urgency_score, x.created_at), reverse=True)

        return AnalyticsOverview(
            total_entries=total,
            critical_alerts_count=critical_count,
            average_urgency=avg_urgency,
            category_distribution=cat_dist,
            sentiment_distribution=sent_dist,
            urgency_distribution=urg_dist,
            recent_critical_alerts=critical_alerts[:10],
        )

    def reset_to_seed(self):
        """Clears all records and reloads default seeds."""
        with self._lock:
            self._cache.clear()
            with self._get_connection() as conn:
                conn.execute("DELETE FROM feedback_entries")
                conn.commit()
        self.load_seed_data()


# Global singleton repository instance
repository = FeedbackRepository()
