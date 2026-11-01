# 📡 Signal2Insight — AI-Powered Civic Engagement Intelligence

> **ImpactHack 2026 Submission**  
> Turning unstructured citizen signals into prioritized, actionable municipal intelligence in real-time.

---

## 🌟 Overview

Cities receive thousands of unstructured messages daily across text, web forms, and hotline voicemails. Most municipal systems struggle to triage emergencies fast enough or spot emerging neighborhood hazards before they escalate.

**Signal2Insight** solves this by:
1. **Ingesting Unstructured Feedback:** Accepts raw text messages, web complaints, and audio voicemails.
2. **AI Structured Extraction:** Analyzes feedback using LLMs (OpenAI / Gemini) with strict Pydantic v2 schemas.
3. **Emergency Hazard Triage:** Automatically flags urgent safety risks (`urgency_score >= 4` or immediate danger) into a real-time Critical Alert Banner.
4. **Actionable Recommendations:** Generates clear 1-sentence summaries and department-specific action steps for city officials.
5. **Interactive Civic Dashboard:** Visualizes sentiment, category breakdowns, urgency heatmaps, and priority feeds.

---

## 🏗️ Architecture

```
Signal2Insight/
├── app/
│   ├── config.py             # Settings & environment variables
│   ├── main.py               # FastAPI application entrypoint + web dashboard
│   ├── models/
│   │   └── schemas.py        # Strict Pydantic v2 schemas & validators
│   ├── routes/
│   │   ├── feedback.py       # Ingest, batch ingest, audio, query & delete endpoints
│   │   └── analytics.py      # KPI metrics, alert feeds, and trend breakdown
│   ├── services/
│   │   ├── llm_engine.py     # Async LLM parser (OpenAI/Gemini) + Smart Mock fallback
│   │   └── audio_service.py  # Audio transcription (Whisper + mock fallback)
│   └── storage/
│       └── repository.py     # SQLite persistence with fast in-memory caching
├── data/
│   └── seed_data.json        # Realistic civic feedback seed records
├── frontend/
│   └── dashboard.py          # Interactive Streamlit civic dashboard (Plotly + KPI cards)
├── tests/
│   └── test_pipeline.py      # Automated Pytest test suite
├── run.py                    # Multi-process CLI launcher
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variables template
```

---

## 📐 Pydantic Data Schema

Every feedback signal analyzed by the pipeline adheres to the following specification:

| Field | Type | Description |
|---|---|---|
| `entry_id` | `str` | Unique record identifier (e.g., `fb_safe001`) |
| `category` | `FeedbackCategory` | `Infrastructure`, `Public Health`, `Education`, `Safety`, `Governance`, `Environment` |
| `sentiment` | `SentimentType` | `Positive`, `Neutral`, `Negative` |
| `urgency_score`| `int (1..5)` | 1 (low/praise) to 5 (immediate public danger) |
| `is_critical_alert` | `bool` | Automatically enforced `True` if `urgency_score >= 4` |
| `summary` | `str` | Exactly 1 concise sentence summarizing the core issue |
| `recommended_action` | `str` | Concrete next step for city or community officials |

---

## 🚀 Quickstart Guide

### 1. Prerequisites & Virtual Environment
```bash
# Clone or navigate to the directory
cd Signal2Insight

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
*Note: If no API keys are provided, Signal2Insight automatically uses its built-in heuristic AI mock engine, guaranteeing 100% uptime for presentations without API rate limits or costs!*

### 3. Launching the System

You can run the full stack with a single command:
```bash
python run.py all
```

Or run individual services:
- **FastAPI Backend & Built-in Web UI:**
  ```bash
  python run.py api
  ```
  - API Root: `http://localhost:8000`
  - Swagger Docs: `http://localhost:8000/docs`
  - Built-in Web Dashboard: `http://localhost:8000/dashboard`

- **Streamlit Data Dashboard:**
  ```bash
  python run.py dashboard
  ```
  - Streamlit UI: `http://localhost:8501`

### 4. Running Automated Tests
```bash
pytest -v tests/test_pipeline.py
```

---

## 📡 API Endpoints

### Ingestion & Query
- `POST /api/feedback/ingest` — Ingest raw feedback text, trigger AI analysis, return validated Pydantic record.
- `POST /api/feedback/ingest-audio` — Ingest `.wav`/`.mp3` audio recording or voicemail.
- `POST /api/feedback/batch` — Batch ingest multiple community submissions concurrently with `asyncio.gather`.
- `GET /api/feedback` — Query and filter entries (`category`, `sentiment`, `is_critical_alert`, `search`, etc.).
- `GET /api/feedback/{entry_id}` — Retrieve detailed feedback record by ID.
- `DELETE /api/feedback/{entry_id}` — Delete a record.
- `POST /api/feedback/reset` — Reset storage back to realistic demonstration seed dataset.

### Analytics & Alerts
- `GET /api/analytics/overview` — Aggregated counts, critical alerts, category/sentiment distributions, and urgency breakdown.
- `GET /api/analytics/critical-alerts` — Instant feed of all active critical emergencies.
- `GET /api/analytics/breakdown` — Category × Sentiment cross-tabulation matrix.
- `GET /health` — Service health check.

---

## 🏆 Hackathon Highlights
- **Resilient AI Fallback:** Never crashes if LLM keys are absent, expired, or rate-limited.
- **Async First:** High-throughput async endpoints capable of handling sudden spikes during civic events.
- **Dual Dashboard Modes:** Includes both an interactive Streamlit app and a lightweight Tailwind/Chart.js web dashboard served directly from FastAPI.
